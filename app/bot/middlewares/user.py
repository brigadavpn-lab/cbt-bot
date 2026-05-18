from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import User


class UserMiddleware(BaseMiddleware):
    """Fetches or creates a User row for the Telegram user. Requires DbSessionMiddleware."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if tg_user is None or session is None:
            return await handler(event, data)

        stmt = (
            pg_insert(User)
            .values(tg_id=tg_user.id)
            .on_conflict_do_nothing(index_elements=["tg_id"])
        )
        await session.execute(stmt)

        result = await session.execute(select(User).where(User.tg_id == tg_user.id))
        data["user"] = result.scalar_one()

        return await handler(event, data)
