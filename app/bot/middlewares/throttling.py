import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """In-memory per-user throttling. Drops events that come faster than rate_seconds."""

    def __init__(self, rate_seconds: float = 1.0) -> None:
        self.rate_seconds = rate_seconds
        self._last_ts: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last_ts.get(user.id, 0.0)
        if now - last < self.rate_seconds:
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Подождите секунду…", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("⏳ Подождите секунду перед следующим запросом.")
            return None

        self._last_ts[user.id] = now
        return await handler(event, data)
