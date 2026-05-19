from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.config import settings


class IsAdmin(BaseFilter):
    """Allows the handler only for the configured ADMIN_TG_ID.

    Supports both Message and CallbackQuery (and any TelegramObject with
    `from_user`).
    """

    async def __call__(self, obj: TelegramObject) -> bool:
        user = getattr(obj, "from_user", None)
        if user is None and isinstance(obj, CallbackQuery):
            user = obj.from_user
        if user is None and isinstance(obj, Message):
            user = obj.from_user
        return bool(user and user.id == settings.ADMIN_TG_ID)
