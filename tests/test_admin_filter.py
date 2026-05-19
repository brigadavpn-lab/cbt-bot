from types import SimpleNamespace

from app.bot.filters.admin import IsAdmin
from app.core.config import settings


async def test_is_admin_accepts_admin():
    f = IsAdmin()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=settings.ADMIN_TG_ID))
    assert await f(msg) is True


async def test_is_admin_rejects_other():
    f = IsAdmin()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=settings.ADMIN_TG_ID + 1))
    assert await f(msg) is False


async def test_is_admin_rejects_anonymous():
    f = IsAdmin()
    msg = SimpleNamespace(from_user=None)
    assert await f(msg) is False
