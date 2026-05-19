import logging

from aiogram import Bot
from aiohttp import web
from sqlalchemy import select

from app.db.models import User
from app.db.session import AsyncSessionLocal
from app.services.payments import PLANS, activate_plan, verify_yukassa_payment

logger = logging.getLogger(__name__)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "bot": "CBT_Trainer"})


async def yukassa_webhook(request: web.Request) -> web.Response:
    """Receives YooKassa payment notifications.

    Security model: YooKassa doesn't sign webhooks. We re-fetch the payment via
    the YooKassa API to verify status before activating the plan. Idempotency
    is enforced by UNIQUE(external_payment_id) on payment_logs.
    """
    try:
        data = await request.json()
    except Exception:
        logger.warning("YooKassa webhook: invalid JSON")
        return web.json_response({"status": "bad_request"}, status=400)

    if data.get("event") != "payment.succeeded":
        return web.json_response({"status": "ignored"})

    obj = data.get("object") or {}
    payment_id = obj.get("id")
    if not payment_id:
        return web.json_response({"status": "no_payment_id"}, status=400)

    verified = await verify_yukassa_payment(payment_id)
    if verified is None or verified["status"] != "succeeded":
        logger.warning("YooKassa webhook: verification failed for %s", payment_id)
        return web.json_response({"status": "unverified"}, status=400)

    metadata = verified["metadata"]
    try:
        tg_id = int(metadata["tg_id"])
        plan_key = metadata["plan"]
    except (KeyError, TypeError, ValueError):
        logger.warning("YooKassa webhook: bad metadata %s", metadata)
        return web.json_response({"status": "bad_metadata"}, status=400)

    if plan_key not in PLANS:
        return web.json_response({"status": "unknown_plan"}, status=400)

    bot: Bot = request.app["bot"]
    activated = False
    expires_at = None

    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if user is None:
            logger.warning("YooKassa webhook: user %s not found", tg_id)
            return web.json_response({"status": "user_not_found"}, status=404)

        activated = await activate_plan(
            s,
            user=user,
            plan_key=plan_key,
            payment_method="yukassa",
            external_payment_id=payment_id,
            amount_rub=verified["amount_rub"],
        )
        await s.commit()
        expires_at = user.plan_expires_at

    if activated and expires_at is not None:
        try:
            await bot.send_message(
                tg_id,
                "✅ <b>Оплата прошла успешно!</b>\n\n"
                f"Безлимитный доступ активирован до "
                f"{expires_at.strftime('%d.%m.%Y')}.",
            )
        except Exception:
            logger.exception("Failed to notify user %s about activation", tg_id)

    return web.json_response({"status": "ok", "activated": activated})


def create_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/health", health)
    app.router.add_post("/yukassa/webhook", yukassa_webhook)
    return app
