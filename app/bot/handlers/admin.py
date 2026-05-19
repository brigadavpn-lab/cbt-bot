import logging
from datetime import UTC, datetime, timedelta

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.db.models import PaymentLog, UsageLog, User
from app.services.payments import PLANS

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("stats"), IsAdmin())
async def admin_stats(message: types.Message, session: AsyncSession):
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = await session.scalar(select(func.count(User.id))) or 0
    paid_users = (
        await session.scalar(
            select(func.count(User.id)).where(
                User.plan == "paid",
                User.plan_expires_at > now,
            )
        )
        or 0
    )

    total_cost = await session.scalar(select(func.sum(UsageLog.cost_usd))) or 0
    total_input = await session.scalar(select(func.sum(UsageLog.input_tokens))) or 0
    total_output = await session.scalar(select(func.sum(UsageLog.output_tokens))) or 0

    today_cost = (
        await session.scalar(
            select(func.sum(UsageLog.cost_usd)).where(UsageLog.created_at >= today_start)
        )
        or 0
    )
    today_requests = (
        await session.scalar(
            select(func.count(UsageLog.id)).where(UsageLog.created_at >= today_start)
        )
        or 0
    )

    total_revenue_rub = (
        await session.scalar(
            select(func.sum(PaymentLog.amount_rub)).where(PaymentLog.status == "succeeded")
        )
        or 0
    )
    total_revenue_stars = (
        await session.scalar(
            select(func.sum(PaymentLog.amount_stars)).where(PaymentLog.status == "succeeded")
        )
        or 0
    )

    text = (
        "📊 <b>Статистика CBT-Gym</b>\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"  Всего: {total_users}\n"
        f"  Платных: {paid_users}\n\n"
        "💰 <b>Выручка:</b>\n"
        f"  ₽: {total_revenue_rub}\n"
        f"  ⭐: {total_revenue_stars}\n\n"
        "🤖 <b>Расходы на Claude API:</b>\n"
        f"  Итого: ${float(total_cost):.4f}\n"
        f"  За сегодня: ${float(today_cost):.4f}\n"
        f"  Запросов сегодня: {today_requests}\n\n"
        "📈 <b>Токены всего:</b>\n"
        f"  Input: {total_input:,}\n"
        f"  Output: {total_output:,}"
    )

    await message.answer(text)


@router.message(Command("userinfo"), IsAdmin())
async def admin_userinfo(message: types.Message, session: AsyncSession):
    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Использование: /userinfo &lt;tg_id&gt;")
        return

    try:
        tg_id = int(args[1])
    except ValueError:
        await message.answer("tg_id должен быть числом")
        return

    target = (await session.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if target is None:
        await message.answer(f"Пользователь {tg_id} не найден")
        return

    user_cost = (
        await session.scalar(select(func.sum(UsageLog.cost_usd)).where(UsageLog.tg_id == tg_id))
        or 0
    )
    user_requests = (
        await session.scalar(select(func.count(UsageLog.id)).where(UsageLog.tg_id == tg_id)) or 0
    )

    plan_info = target.plan
    if target.plan_expires_at:
        plan_info += f" до {target.plan_expires_at.strftime('%d.%m.%Y')}"

    username = f"@{target.username}" if target.username else "—"
    created = target.created_at.strftime("%d.%m.%Y") if target.created_at else "—"

    text = (
        f"👤 <b>Пользователь {tg_id}</b>\n\n"
        f"Имя: {target.full_name or '—'}\n"
        f"Username: {username}\n"
        f"Зарегистрирован: {created}\n\n"
        f"📋 План: {plan_info}\n"
        f"📊 Сегодня: ситуаций {target.situation_requests_today}, "
        f"генераций {target.generator_requests_today}\n"
        f"⭐ XP: {target.xp} | Уровень: {target.level}\n"
        f"🔥 Серия: {target.streak} (рекорд {target.max_streak})\n\n"
        f"🤖 Запросов к ИИ: {user_requests}\n"
        f"💸 Потрачено на API: ${float(user_cost):.4f}"
    )

    await message.answer(text)


@router.message(Command("setplan"), IsAdmin())
async def admin_setplan(message: types.Message, session: AsyncSession):
    args = (message.text or "").split()
    if len(args) < 3:
        await message.answer("Использование: /setplan &lt;tg_id&gt; &lt;weekly|monthly|free&gt;")
        return

    try:
        tg_id = int(args[1])
    except ValueError:
        await message.answer("tg_id должен быть числом")
        return

    plan_key = args[2]
    if plan_key not in PLANS and plan_key != "free":
        await message.answer(f"Неизвестный план: {plan_key}. Доступны: weekly, monthly, free")
        return

    target = (await session.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if target is None:
        await message.answer(f"Пользователь {tg_id} не найден")
        return

    if plan_key == "free":
        target.plan = "free"
        target.plan_expires_at = None
        await message.answer(f"✅ Пользователю {tg_id} установлен план free")
    else:
        target.plan = "paid"
        target.plan_expires_at = datetime.now(UTC) + timedelta(days=PLANS[plan_key]["days"])
        await message.answer(
            f"✅ Пользователю {tg_id} активирован план {plan_key} "
            f"до {target.plan_expires_at.strftime('%d.%m.%Y')}"
        )
        try:
            await message.bot.send_message(tg_id, "✅ Ваш доступ активирован администратором!")
        except Exception:
            logger.exception("Failed to notify user %s", tg_id)
