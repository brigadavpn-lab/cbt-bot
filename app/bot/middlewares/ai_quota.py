import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class AiQuotaMiddleware(BaseMiddleware):
    """Enforces a per-user daily limit for AI requests via Redis INCR/EXPIRE."""

    def __init__(self, redis_url: str | None, daily_limit: int) -> None:
        self.daily_limit = daily_limit
        self._redis: Redis | None = Redis.from_url(redis_url) if redis_url else None

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if self._redis is None or self.daily_limit <= 0:
            return await handler(event, data)

        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        key = f"ai_quota:{tg_user.id}"
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 24 * 60 * 60)
        except Exception:
            logger.exception("AI quota Redis call failed; allowing request")
            return await handler(event, data)

        if count > self.daily_limit:
            msg = (
                f"📊 Дневной лимит AI-запросов исчерпан ({self.daily_limit}). "
                "Возвращайтесь завтра."
            )
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(msg)
            return None

        return await handler(event, data)
