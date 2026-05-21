from collections import defaultdict
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Message


class RateLimitMiddleware(BaseMiddleware):
    """
    Ограничивает количество сообщений от одного пользователя.
    По умолчанию: не более 10 сообщений за 60 секунд.
    При превышении — отвечает предупреждением и не передаёт событие дальше.
    Применяется только к Message (callback_query не считаются).
    """

    def __init__(self, limit: int = 10, period: int = 60):
        self.limit = limit
        self.period = period
        self.user_messages: dict[int, list[datetime]] = defaultdict(list)

    async def __call__(self, handler, event, data):
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        now = datetime.now()
        cutoff = now - timedelta(seconds=self.period)

        # Очищаем старые таймстемпы
        self.user_messages[user_id] = [
            t for t in self.user_messages[user_id] if t > cutoff
        ]

        if len(self.user_messages[user_id]) >= self.limit:
            try:
                await event.answer("⏳ Не так быстро! Подожди немного.")
            except Exception:
                pass
            return

        self.user_messages[user_id].append(now)
        return await handler(event, data)
