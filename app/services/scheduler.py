import glob
import logging
import os
import subprocess
import time
import urllib.parse
from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

PRICE_INPUT_PER_TOKEN = 0.000003   # $3 за 1M input токенов
PRICE_OUTPUT_PER_TOKEN = 0.000015  # $15 за 1M output токенов

BACKUP_DIR = '/root/backups/cbt-bot'
BACKUP_RETENTION_DAYS = 7


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


async def check_monthly_spend():
    """Проверка расхода за месяц каждые 6 часов. Уведомляет один раз в месяц через Redis-ключ."""
    if not settings.ADMIN_TG_ID:
        return
    if not settings.REDIS_URL:
        logger.warning("check_monthly_spend: REDIS_URL not set, skipping")
        return

    import redis.asyncio as aioredis

    year_month = date.today().strftime("%Y-%m")
    alert_key = f"spend_alert_sent:{year_month}"

    redis_client = aioredis.from_url(settings.REDIS_URL)
    already_sent = await redis_client.exists(alert_key)
    if already_sent:
        await redis_client.aclose()
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
                "FROM token_usage "
                "WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)"
            )
        )
        row = result.fetchone()
        input_t, output_t = row[0], row[1]

    cost = input_t * PRICE_INPUT_PER_TOKEN + output_t * PRICE_OUTPUT_PER_TOKEN

    if cost >= settings.MONTHLY_SPEND_ALERT_USD:
        from app.main import bot  # lazy import
        alert_text = (
            f"🚨 <b>Превышен лимит расходов!</b>\n\n"
            f"Расход за {year_month}: <b>${cost:.2f}</b>\n"
            f"Лимит: ${settings.MONTHLY_SPEND_ALERT_USD:.2f}\n\n"
            f"Проверьте использование API."
        )
        try:
            await bot.send_message(settings.ADMIN_TG_ID, alert_text, parse_mode="HTML")
            await redis_client.set(alert_key, 1, ex=35 * 24 * 3600)
            logger.warning("Monthly spend alert sent: $%.2f", cost)
        except Exception as e:
            logger.error("Failed to send spend alert: %s", type(e).__name__)

    await redis_client.aclose()


def _cleanup_old_backups():
    cutoff = time.time() - BACKUP_RETENTION_DAYS * 86400
    removed = 0
    for f in glob.glob(f'{BACKUP_DIR}/cbt_db_*.sql.gz'):
        if os.path.getmtime(f) < cutoff:
            os.remove(f)
            removed += 1
            logger.info('backup_database: removed old backup %s', f)
    if removed:
        logger.info('backup_database: cleaned up %d old backups', removed)


async def backup_database():
    """Еженедельный бэкап PostgreSQL. Воскресенье 20:00 UTC (23:00 МСК)."""
    logger.info('backup_database: starting weekly backup')
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # DATABASE_URL — str, не SecretStr
    parsed = urllib.parse.urlparse(settings.DATABASE_URL.replace('+asyncpg', ''))
    pg_user = parsed.username
    pg_dbname = parsed.path.lstrip('/')

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    backup_file = f'{BACKUP_DIR}/cbt_db_{timestamp}.sql.gz'

    try:
        with open(backup_file, 'wb') as f:
            dump_proc = subprocess.Popen(
                ['docker', 'exec', 'cbt-bot-db-1',
                 'pg_dump', '-U', pg_user, '-d', pg_dbname],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            gzip_proc = subprocess.Popen(
                ['gzip', '-c'],
                stdin=dump_proc.stdout,
                stdout=f,
                stderr=subprocess.PIPE,
            )
            dump_proc.stdout.close()
            gzip_proc.communicate()
            dump_proc.wait()

        if dump_proc.returncode != 0:
            logger.error('backup_database: pg_dump failed (rc=%d), removing partial file',
                         dump_proc.returncode)
            os.remove(backup_file)
            return

        size_kb = os.path.getsize(backup_file) // 1024
        logger.info('backup_database: created %s (%d KB)', backup_file, size_kb)
        _cleanup_old_backups()

        if settings.ADMIN_TG_ID:
            from app.main import bot
            await bot.send_message(
                settings.ADMIN_TG_ID,
                f'✅ <b>Еженедельный бэкап выполнен</b>\n\n'
                f'📁 Файл: <code>{os.path.basename(backup_file)}</code>\n'
                f'📦 Размер: {size_kb} KB',
                parse_mode='HTML',
            )

    except Exception as e:
        logger.error('backup_database: unexpected error: %s', type(e).__name__)
        if os.path.exists(backup_file):
            os.remove(backup_file)
        if settings.ADMIN_TG_ID:
            from app.main import bot
            try:
                await bot.send_message(
                    settings.ADMIN_TG_ID,
                    f'❌ <b>Ошибка бэкапа!</b>\n{type(e).__name__}',
                    parse_mode='HTML',
                )
            except Exception:
                pass


def setup_scheduler():
    scheduler.add_job(send_daily_report, CronTrigger(hour=19, minute=0))
    scheduler.add_job(check_monthly_spend, CronTrigger(hour="*/6", minute=0))
    scheduler.add_job(backup_database, CronTrigger(day_of_week='sun', hour=20, minute=0))
    scheduler.start()
    logger.info("Scheduler started: daily report at 19:00 UTC (22:00 MSK)")
    logger.info("Scheduler: spend check every 6 hours")
    logger.info("Scheduler: weekly backup every Sunday at 20:00 UTC (23:00 MSK)")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
