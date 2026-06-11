import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

PRICE_INPUT_PER_TOKEN = 0.000003   # $3 за 1M input токенов
PRICE_OUTPUT_PER_TOKEN = 0.000015  # $15 за 1M output токенов


async def send_daily_report():
    """Ежедневный отчёт в 22:00 МСК (19:00 UTC)."""
    if not settings.ADMIN_TG_ID:
        logger.warning("send_daily_report: ADMIN_TG_ID not set, skipping")
        return

    today = date.today()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COUNT(*) "
                "FROM token_usage WHERE DATE(created_at) = :today"
            ),
            {"today": today},
        )
        row = result.fetchone()
        input_t, output_t, requests = row[0], row[1], row[2]

    cost_today = input_t * PRICE_INPUT_PER_TOKEN + output_t * PRICE_OUTPUT_PER_TOKEN
    text_msg = (
        f'📊 <b>Ежедневный отчёт — {today.strftime("%d.%m.%Y")}</b>\n\n'
        f"<b>Сегодня:</b>\n"
        f"• Запросов к Claude: {requests}\n"
        f"• Токенов: {input_t:,} input / {output_t:,} output\n"
        f"• Стоимость: ${cost_today:.4f}"
    )

    from app.main import bot  # lazy import: app.main импортирует scheduler, обратного нет
    try:
        await bot.send_message(settings.ADMIN_TG_ID, text_msg, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to send daily report: %s", type(e).__name__)


def setup_scheduler():
    scheduler.add_job(send_daily_report, CronTrigger(hour=19, minute=0))
    scheduler.start()
    logger.info("Scheduler started: daily report at 19:00 UTC (22:00 MSK)")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
