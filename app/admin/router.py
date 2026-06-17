import asyncio
import json
import secrets as py_secrets
from datetime import datetime, timezone, timedelta, date

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import quote as url_quote

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.admin.auth import verify_admin
from app.db.models import Attempt, ReactivationCampaign, ReactivationLog, Task, TokenUsage, User
from app.db.session import AsyncSessionLocal
from app.services.reactivation import send_reactivation_campaign
from app.utils.html import esc

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/admin/templates")
templates.env.globals["now"] = datetime.utcnow()


def to_moscow(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt + timedelta(hours=3)


templates.env.filters['moscow'] = to_moscow


def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


# ─── Дашборд ────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, admin: str = Depends(verify_admin)):
    async with AsyncSessionLocal() as s:
        total_users = (await s.execute(text("SELECT COUNT(*) FROM users"))).scalar()
        new_7d = (await s.execute(
            text("SELECT COUNT(*) FROM users WHERE created_at > now() - interval '7 days'")
        )).scalar()
        active_today = (await s.execute(
            text("SELECT COUNT(*) FROM users WHERE last_active_at > now() - interval '24 hours'")
        )).scalar()

        row = (await s.execute(
            text("SELECT COUNT(*), COALESCE(SUM(input_tokens+output_tokens),0) FROM token_usage")
        )).fetchone()
        total_requests, total_tokens = row[0], row[1]

        row_today = (await s.execute(
            text("SELECT COUNT(*), COALESCE(SUM(input_tokens+output_tokens),0) FROM token_usage "
                 "WHERE created_at > now() - interval '24 hours'")
        )).fetchone()
        requests_today = row_today[0]

        row_month = (await s.execute(
            text("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
                 "FROM token_usage "
                 "WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)")
        )).fetchone()
        input_month, output_month = row_month[0], row_month[1]
        cost_month = round(input_month * 0.000003 + output_month * 0.000015, 2)

        active_tasks = (await s.execute(
            text("SELECT COUNT(*) FROM tasks WHERE active=true")
        )).scalar()
        total_tasks = (await s.execute(text("SELECT COUNT(*) FROM tasks"))).scalar()

        top3 = (await s.execute(
            text("SELECT payload->>'correct_cognitive_distortion' as d, COUNT(*) as cnt "
                 "FROM tasks WHERE active=true GROUP BY 1 ORDER BY cnt DESC LIMIT 3")
        )).fetchall()
        top3_max = top3[0][1] if top3 else 1

    response = templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "total_users": total_users,
        "new_7d": new_7d,
        "active_today": active_today,
        "total_requests": total_requests,
        "requests_today": requests_today,
        "input_month": input_month,
        "output_month": output_month,
        "cost_month": cost_month,
        "active_tasks": active_tasks,
        "total_tasks": total_tasks,
        "top3": top3,
        "top3_max": top3_max,
    })
    return _add_security_headers(response)


# ─── Пользователи ───────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    admin: str = Depends(verify_admin),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    async with AsyncSessionLocal() as s:
        sql = (
            "SELECT u.id, u.tg_id, u.full_name, u.level, u.xp, u.streak, "
            "       u.created_at, u.last_active_at, "
            "       COUNT(t.id) as total_requests, "
            "       COALESCE(SUM(t.input_tokens + t.output_tokens), 0) as total_tokens, "
            "       u.is_blocked "
            "FROM users u "
            "LEFT JOIN token_usage t ON t.user_id = u.id "
        )
        params: dict = {}
        where_clauses = []
        if date_from:
            where_clauses.append("u.last_active_at >= :date_from")
            params["date_from"] = date.fromisoformat(date_from)
        if date_to:
            from datetime import timedelta
            date_to_end = date.fromisoformat(date_to) + timedelta(days=1)
            where_clauses.append("u.last_active_at < :date_to_end")
            params["date_to_end"] = date_to_end
        if where_clauses:
            sql += "WHERE " + " AND ".join(where_clauses) + " "
        sql += "GROUP BY u.id ORDER BY u.last_active_at DESC NULLS LAST"
        rows = (await s.execute(text(sql), params)).fetchall()

    now = datetime.now(timezone.utc)

    def activity_color(last_active):
        if last_active is None:
            return "red"
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        delta = now - last_active
        if delta.total_seconds() < 86400:
            return "green"
        if delta.days < 7:
            return "yellow"
        return "red"

    users = [
        {
            "id": r[0], "tg_id": r[1],
            "full_name": r[2] or None,
            "level": r[3], "xp": r[4], "streak": r[5],
            "created_at": r[6], "last_active_at": r[7],
            "total_requests": r[8], "total_tokens": r[9],
            "color": activity_color(r[7]),
            "is_blocked": r[10],
        }
        for r in rows
    ]

    csrf_token = py_secrets.token_hex(32)
    response = templates.TemplateResponse("users.html", {
        "request": request,
        "active_page": "users",
        "users": users,
        "csrf_token": csrf_token,
        "date_from": date_from or "",
        "date_to": date_to or "",
        "total_count": len(users),
    })
    response.set_cookie("csrf_token", csrf_token, httponly=True, samesite="strict", max_age=3600)
    return _add_security_headers(response)


@router.post("/users/{user_id}/block", response_class=HTMLResponse)
async def block_user(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    admin: str = Depends(verify_admin),
    date_from: str = Form(default=""),
    date_to: str = Form(default=""),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен")
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_blocked = True
            await session.commit()
    redirect_url = "/admin/users"
    qs = "&".join(f"{k}={v}" for k, v in [("date_from", date_from), ("date_to", date_to)] if v)
    if qs:
        redirect_url += "?" + qs
    return RedirectResponse(redirect_url, status_code=303)


@router.post("/users/{user_id}/unblock", response_class=HTMLResponse)
async def unblock_user(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    admin: str = Depends(verify_admin),
    date_from: str = Form(default=""),
    date_to: str = Form(default=""),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен")
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_blocked = False
            await session.commit()
    redirect_url = "/admin/users"
    qs = "&".join(f"{k}={v}" for k, v in [("date_from", date_from), ("date_to", date_to)] if v)
    if qs:
        redirect_url += "?" + qs
    return RedirectResponse(redirect_url, status_code=303)


# ─── Токены ─────────────────────────────────────────────────────────────────

@router.get("/tokens", response_class=HTMLResponse)
async def tokens_page(request: Request, admin: str = Depends(verify_admin)):
    async with AsyncSessionLocal() as s:
        daily_rows = (await s.execute(text(
            "SELECT DATE(created_at) as day, "
            "       SUM(input_tokens) as inp, SUM(output_tokens) as out, COUNT(*) as req "
            "FROM token_usage "
            "GROUP BY DATE(created_at) "
            "ORDER BY day DESC LIMIT 14"
        ))).fetchall()
        daily_rows = list(reversed(daily_rows))

        by_feature = (await s.execute(text(
            "SELECT feature, COUNT(*) as cnt, "
            "       COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
            "FROM token_usage GROUP BY feature"
        ))).fetchall()

        top_users = (await s.execute(text(
            "SELECT u.full_name, u.tg_id, "
            "       COALESCE(SUM(t.input_tokens+t.output_tokens),0) as total "
            "FROM token_usage t "
            "JOIN users u ON u.id = t.user_id "
            "GROUP BY u.id, u.full_name, u.tg_id "
            "ORDER BY total DESC LIMIT 10"
        ))).fetchall()

    chart_labels = json.dumps([str(r[0]) for r in daily_rows])
    chart_input = json.dumps([int(r[1]) for r in daily_rows])
    chart_output = json.dumps([int(r[2]) for r in daily_rows])

    features = {r[0]: {"cnt": r[1], "input": r[2], "output": r[3]} for r in by_feature}

    response = templates.TemplateResponse("tokens.html", {
        "request": request,
        "active_page": "tokens",
        "chart_labels": chart_labels,
        "chart_input": chart_input,
        "chart_output": chart_output,
        "features": features,
        "top_users": top_users,
    })
    return _add_security_headers(response)


# ─── Задачи ─────────────────────────────────────────────────────────────────

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, admin: str = Depends(verify_admin)):
    async with AsyncSessionLocal() as s:
        distrib = (await s.execute(text(
            "SELECT payload->>'correct_cognitive_distortion' as d, "
            "       COUNT(*) as cnt, "
            "       SUM(CASE WHEN active THEN 1 ELSE 0 END) as active_cnt "
            "FROM tasks GROUP BY d ORDER BY cnt DESC"
        ))).fetchall()

        total_tasks = (await s.execute(text("SELECT COUNT(*) FROM tasks"))).scalar()
        active_tasks = (await s.execute(text("SELECT COUNT(*) FROM tasks WHERE active=true"))).scalar()
        used_tasks = (await s.execute(text(
            "SELECT COUNT(DISTINCT task_id) FROM attempts"
        ))).scalar()

    labels = json.dumps([r[0] or "Неизвестно" for r in distrib])
    data = json.dumps([int(r[1]) for r in distrib])

    response = templates.TemplateResponse("tasks.html", {
        "request": request,
        "active_page": "tasks",
        "chart_labels": labels,
        "chart_data": data,
        "distrib": distrib,
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "inactive_tasks": total_tasks - active_tasks,
        "used_tasks": used_tasks,
    })
    return _add_security_headers(response)


# ─── Рассылка ────────────────────────────────────────────────────────────────

@router.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request, admin: str = Depends(verify_admin)):
    csrf_token = py_secrets.token_hex(32)
    response = templates.TemplateResponse("broadcast.html", {
        "request": request,
        "active_page": "broadcast",
        "result": None,
        "csrf_token": csrf_token,
    })
    response.set_cookie("csrf_token", csrf_token, httponly=True, samesite="strict", max_age=3600)
    return _add_security_headers(response)


@router.post("/broadcast/send", response_class=HTMLResponse)
async def broadcast_send(
    request: Request,
    text_msg: str = Form(..., alias="text"),
    personalize: str = Form(default=""),
    csrf_token: str = Form(...),
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    admin: str = Depends(verify_admin),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен")

    from app.main import bot

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(
            "SELECT tg_id, full_name FROM users WHERE is_blocked = false"
        ))).fetchall()

    sent = 0
    errors = 0
    do_personalize = bool(personalize)

    for tg_id, full_name in rows:
        msg = text_msg
        if do_personalize and "{name}" in msg:
            name = esc(full_name or "Пользователь")
            msg = msg.replace("{name}", name)
        try:
            await bot.send_message(chat_id=tg_id, text=msg, parse_mode="HTML")
            sent += 1
        except Exception:
            errors += 1
        await asyncio.sleep(0.05)

    new_csrf = py_secrets.token_hex(32)
    response = templates.TemplateResponse("broadcast.html", {
        "request": request,
        "active_page": "broadcast",
        "result": {"sent": sent, "errors": errors},
        "csrf_token": new_csrf,
    })
    response.set_cookie("csrf_token", new_csrf, httponly=True, samesite="strict", max_age=3600)
    return _add_security_headers(response)


# ─── Реактивационные рассылки ────────────────────────────────────────────────

DAYS_MAP = {'mon': 'Пн', 'tue': 'Вт', 'wed': 'Ср', 'thu': 'Чт', 'fri': 'Пт', 'sat': 'Сб', 'sun': 'Вс'}


@router.get('/reactivation', response_class=HTMLResponse)
async def reactivation_page(
    request: Request,
    admin=Depends(verify_admin),
    result_sent: int = 0,
    result_errors: int = 0,
    result_campaign: str = '',
):
    async with AsyncSessionLocal() as s:
        campaigns = (await s.execute(
            select(ReactivationCampaign).order_by(ReactivationCampaign.days_inactive)
        )).scalars().all()

        stats = {}
        for c in campaigns:
            sent_count = (await s.execute(
                select(func.count()).select_from(ReactivationLog)
                .where(ReactivationLog.campaign_id == c.id)
            )).scalar() or 0
            eligible = (await s.execute(text(
                'SELECT COUNT(*) FROM users u '
                'WHERE u.is_blocked = false '
                "AND u.last_active_at < now() - :days * interval '1 day' "
                'AND u.id NOT IN ('
                '  SELECT user_id FROM reactivation_log WHERE campaign_id = :cid'
                ')'
            ), {'days': c.days_inactive, 'cid': c.id})).scalar() or 0
            stats[c.id] = {'sent': sent_count, 'eligible': eligible}

    csrf_token = py_secrets.token_hex(32)
    response = templates.TemplateResponse('reactivation.html', {
        'request': request,
        'active_page': 'reactivation',
        'campaigns': campaigns,
        'stats': stats,
        'csrf_token': csrf_token,
        'result_sent': result_sent,
        'result_errors': result_errors,
        'result_campaign': result_campaign,
        'days_map': DAYS_MAP,
    })
    response.set_cookie('csrf_token', csrf_token, httponly=True, samesite='strict', max_age=3600)
    return _add_security_headers(response)


@router.post('/reactivation/create', response_class=HTMLResponse)
async def reactivation_create(
    request: Request,
    name: str = Form(...),
    days_inactive: int = Form(...),
    message_text: str = Form(...),
    schedule_day: str = Form(default=''),
    schedule_hour: str = Form(default=''),
    schedule_minute: str = Form(default='0'),
    csrf_token: str = Form(...),
    csrf_cookie: Optional[str] = Cookie(default=None, alias='csrf_token'),
    admin=Depends(verify_admin),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail='CSRF-токен недействителен')
    async with AsyncSessionLocal() as s:
        campaign = ReactivationCampaign(
            name=esc(name),
            days_inactive=max(1, days_inactive),
            message_text=message_text,
            schedule_day=schedule_day or None,
            schedule_hour=int(schedule_hour) if schedule_hour else None,
            schedule_minute=int(schedule_minute) if schedule_minute else 0,
        )
        s.add(campaign)
        await s.commit()
    return RedirectResponse('/admin/reactivation', status_code=303)


@router.post('/reactivation/{campaign_id}/edit', response_class=HTMLResponse)
async def reactivation_edit(
    campaign_id: int,
    request: Request,
    name: str = Form(...),
    days_inactive: int = Form(...),
    message_text: str = Form(...),
    schedule_day: str = Form(default=''),
    schedule_hour: str = Form(default=''),
    schedule_minute: str = Form(default='0'),
    csrf_token: str = Form(...),
    csrf_cookie: Optional[str] = Cookie(default=None, alias='csrf_token'),
    admin=Depends(verify_admin),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail='CSRF-токен недействителен')
    async with AsyncSessionLocal() as s:
        c = await s.get(ReactivationCampaign, campaign_id)
        if c:
            c.name = esc(name)
            c.days_inactive = max(1, days_inactive)
            c.message_text = message_text
            c.schedule_day = schedule_day or None
            c.schedule_hour = int(schedule_hour) if schedule_hour else None
            c.schedule_minute = int(schedule_minute) if schedule_minute else 0
            await s.commit()
    return RedirectResponse('/admin/reactivation', status_code=303)


@router.post('/reactivation/{campaign_id}/send', response_class=HTMLResponse)
async def reactivation_send(
    campaign_id: int,
    request: Request,
    csrf_token: str = Form(...),
    csrf_cookie: Optional[str] = Cookie(default=None, alias='csrf_token'),
    admin=Depends(verify_admin),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail='CSRF-токен недействителен')
    async with AsyncSessionLocal() as s:
        campaign = await s.get(ReactivationCampaign, campaign_id)
        campaign_name = campaign.name if campaign else ''
    result = await send_reactivation_campaign(campaign_id)
    return RedirectResponse(
        f'/admin/reactivation?result_sent={result["sent"]}'
        f'&result_errors={result["errors"]}&result_campaign={url_quote(campaign_name)}',
        status_code=303,
    )


@router.post('/reactivation/{campaign_id}/toggle', response_class=HTMLResponse)
async def reactivation_toggle(
    campaign_id: int,
    request: Request,
    csrf_token: str = Form(...),
    csrf_cookie: Optional[str] = Cookie(default=None, alias='csrf_token'),
    admin=Depends(verify_admin),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail='CSRF-токен недействителен')
    async with AsyncSessionLocal() as s:
        c = await s.get(ReactivationCampaign, campaign_id)
        if c:
            c.is_active = not c.is_active
            await s.commit()
    return RedirectResponse('/admin/reactivation', status_code=303)


@router.post('/reactivation/{campaign_id}/delete', response_class=HTMLResponse)
async def reactivation_delete(
    campaign_id: int,
    request: Request,
    csrf_token: str = Form(...),
    csrf_cookie: Optional[str] = Cookie(default=None, alias='csrf_token'),
    admin=Depends(verify_admin),
):
    if not csrf_cookie or not py_secrets.compare_digest(csrf_token, csrf_cookie):
        raise HTTPException(status_code=403, detail='CSRF-токен недействителен')
    async with AsyncSessionLocal() as s:
        c = await s.get(ReactivationCampaign, campaign_id)
        if c:
            try:
                await s.delete(c)
                await s.commit()
            except IntegrityError:
                await s.rollback()
                return RedirectResponse(
                    '/admin/reactivation?error=delete_failed', status_code=303
                )
    return RedirectResponse('/admin/reactivation', status_code=303)
