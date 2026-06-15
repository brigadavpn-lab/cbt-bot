import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import AsyncSessionLocal
from app.db.models import ReactivationCampaign, ReactivationLog
from app.utils.html import esc

logger = logging.getLogger(__name__)


async def send_reactivation_campaign(campaign_id: int) -> dict:
    from app.main import bot  # ленивый импорт — избегает circular import

    sent = 0
    errors = 0

    async with AsyncSessionLocal() as session:
        campaign = await session.get(ReactivationCampaign, campaign_id)
        if not campaign or not campaign.is_active:
            return {'sent': 0, 'errors': 0}

        rows = (await session.execute(text(
            'SELECT u.id, u.tg_id, u.full_name FROM users u '
            'WHERE u.is_blocked = false '
            "AND u.last_active_at < now() - :days * interval '1 day' "
            'AND u.id NOT IN ('
            '  SELECT user_id FROM reactivation_log WHERE campaign_id = :cid'
            ')'
        ), {'days': campaign.days_inactive, 'cid': campaign_id})).fetchall()

        for user_id, tg_id, full_name in rows:
            msg = campaign.message_text.replace(
                '{name}', esc(full_name or 'Пользователь')
            )
            success = False
            try:
                await bot.send_message(tg_id, msg, parse_mode='HTML')
                sent += 1
                success = True
            except Exception as e:
                errors += 1
                logger.error('reactivation send error user=%s: %s', tg_id, type(e).__name__)

            try:
                # savepoint: IntegrityError не откатывает предыдущие записи в батче
                async with session.begin_nested():
                    log_entry = ReactivationLog(
                        campaign_id=campaign_id, user_id=user_id, success=success
                    )
                    session.add(log_entry)
            except IntegrityError:
                pass  # уже отправляли — пропускаем

            await asyncio.sleep(0.05)  # rate limit Telegram

        await session.commit()

    logger.info('reactivation: campaign=%d sent=%d errors=%d', campaign_id, sent, errors)
    return {'sent': sent, 'errors': errors}
