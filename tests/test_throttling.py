from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.middlewares.throttling import ThrottlingMiddleware


async def test_throttle_blocks_second_call():
    mw = ThrottlingMiddleware(rate_seconds=10.0)
    user = SimpleNamespace(id=42)
    answer = AsyncMock()
    event = SimpleNamespace(answer=answer)
    handler = AsyncMock(return_value="ok")

    first = await mw(handler, event, {"event_from_user": user})
    second = await mw(handler, event, {"event_from_user": user})

    assert first == "ok"
    assert second is None
    handler.assert_awaited_once()


async def test_throttle_allows_different_users():
    mw = ThrottlingMiddleware(rate_seconds=10.0)
    handler = AsyncMock(return_value="ok")
    e1 = SimpleNamespace(answer=AsyncMock())
    e2 = SimpleNamespace(answer=AsyncMock())

    a = await mw(handler, e1, {"event_from_user": SimpleNamespace(id=1)})
    b = await mw(handler, e2, {"event_from_user": SimpleNamespace(id=2)})

    assert a == "ok" and b == "ok"
    assert handler.await_count == 2


async def test_throttle_passes_through_when_no_user():
    mw = ThrottlingMiddleware(rate_seconds=10.0)
    handler = AsyncMock(return_value="ok")
    result = await mw(handler, SimpleNamespace(), {})
    assert result == "ok"
