from collections import defaultdict
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.core.config import settings


class RateLimitMiddleware(BaseMiddleware):
    """
    Ограничивает количество событий от одного пользователя.
    Использует Redis если REDIS_URL задан, иначе in-memory fallback.
    Применяется к Message и CallbackQuery.
    """

    def __init__(self, limit: int = 10, period: int = 60):
        self.limit = limit
        self.period = period
        self._redis = aioredis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None
        # Fallback in-memory (используется только если Redis недоступен)
        self._user_messages: dict[int, list[datetime]] = defaultdict(list)

    async def __call__(self, handler, event, data):
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        if self._redis is not None:
            blocked = await self._check_redis(user_id)
        else:
            blocked = self._check_memory(user_id)

        if blocked:
            try:
                await event.answer("⏳ Не так быстро! Подожди немного.")
            except Exception:
                pass
            return

        return await handler(event, data)

    async def _check_redis(self, user_id: int) -> bool:
        key = f"rate:{user_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self.period)
        return count > self.limit

    def _check_memory(self, user_id: int) -> bool:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.period)
        self._user_messages[user_id] = [
            t for t in self._user_messages[user_id] if t > cutoff
        ]
        if len(self._user_messages[user_id]) >= self.limit:
            return True
        self._user_messages[user_id].append(now)
        return False
