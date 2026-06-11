import logging

import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class BlockCheckMiddleware(BaseMiddleware):
    """
    Проверяет, заблокирован ли пользователь перед обработкой любого события.
    Использует Redis-кэш (TTL 5 минут) для снижения нагрузки на БД.
    При отсутствии Redis — обращается к БД напрямую.
    """

    def __init__(self):
        self._redis = aioredis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None

    async def __call__(self, handler, event, data):
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user = event.from_user
        if user is None:
            return await handler(event, data)

        tg_id = user.id
        is_blocked = await self._is_blocked(tg_id)

        if is_blocked:
            try:
                await event.answer("🚫 Доступ ограничен. Обратитесь к администратору.")
            except Exception:
                pass
            return

        return await handler(event, data)

    async def _is_blocked(self, tg_id: int) -> bool:
        if self._redis is not None:
            cache_key = f"blocked:{tg_id}"
            cached = await self._redis.get(cache_key)
            if cached is not None:
                return cached == b"1"
            blocked = await self._query_db(tg_id)
            await self._redis.set(cache_key, "1" if blocked else "0", ex=300)
            return blocked

        return await self._query_db(tg_id)

    async def _query_db(self, tg_id: int) -> bool:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("SELECT is_blocked FROM users WHERE tg_id = :tg_id"),
                    {"tg_id": tg_id},
                )
                row = result.fetchone()
                return bool(row[0]) if row else False
        except Exception:
            logger.exception("BlockCheckMiddleware: DB query failed for tg_id=%s", tg_id)
            return False
