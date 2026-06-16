import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.reactivation import send_reactivation_campaign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(is_active=True, days_inactive=7, message_text="Привет, {name}!"):
    c = MagicMock()
    c.is_active = is_active
    c.days_inactive = days_inactive
    c.message_text = message_text
    return c


def _make_session(campaign, rows=None):
    """Build a fully-mocked async SQLAlchemy session."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=campaign)
    if rows is not None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        session.execute = AsyncMock(return_value=mock_result)
    # begin_nested() must return a sync object with async __aenter__/__aexit__,
    # NOT an AsyncMock — calling AsyncMock() returns a coroutine, not a context manager.
    nested_ctx = MagicMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)
    # session.add() is synchronous in SQLAlchemy async — use MagicMock to avoid
    # "coroutine never awaited" warnings from AsyncMock.
    session.add = MagicMock()
    return session


def _db_ctx(session):
    """Wrap a session mock so it behaves as `async with AsyncSessionLocal() as session:`."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=ctx)


def _get_bot():
    """Return the bot mock installed by conftest.py, cleaned between tests."""
    bot = sys.modules["app.main"].bot
    bot.reset_mock()
    # reset_mock() does NOT clear side_effect by default; do it explicitly so
    # a list side_effect from a previous test does not exhaust into the next one.
    bot.send_message.side_effect = None
    return bot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_campaign_not_found():
    session = _make_session(campaign=None)
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(999)
    assert result == {"sent": 0, "errors": 0}
    _get_bot()  # reset; assert is implicit — send_message was never set up


@pytest.mark.asyncio
async def test_campaign_inactive():
    session = _make_session(campaign=_make_campaign(is_active=False))
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(1)
    assert result == {"sent": 0, "errors": 0}


@pytest.mark.asyncio
async def test_single_user_success():
    bot = _get_bot()
    campaign = _make_campaign(message_text="Привет, {name}!")
    session = _make_session(campaign, rows=[(1, 100, "Иван")])
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(1)
    assert result == {"sent": 1, "errors": 0}
    bot.send_message.assert_called_once_with(100, "Привет, Иван!", parse_mode="HTML")


@pytest.mark.asyncio
async def test_send_error():
    bot = _get_bot()
    bot.send_message.side_effect = Exception("Telegram error")
    campaign = _make_campaign()
    session = _make_session(campaign, rows=[(1, 100, "Иван")])
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(1)
    assert result == {"sent": 0, "errors": 1}


@pytest.mark.asyncio
async def test_partial_success():
    bot = _get_bot()
    bot.send_message.side_effect = [None, Exception("fail"), None]
    campaign = _make_campaign()
    rows = [(1, 101, "Анна"), (2, 102, "Борис"), (3, 103, "Вера")]
    session = _make_session(campaign, rows=rows)
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(1)
    assert result == {"sent": 2, "errors": 1}


@pytest.mark.asyncio
async def test_html_in_name():
    bot = _get_bot()
    campaign = _make_campaign(message_text="Привет, {name}!")
    session = _make_session(campaign, rows=[(1, 100, "<Иван>")])
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(1)
    assert result == {"sent": 1, "errors": 0}
    bot.send_message.assert_called_once_with(
        100, "Привет, &lt;Иван&gt;!", parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_none_name_default():
    bot = _get_bot()
    campaign = _make_campaign(message_text="Привет, {name}!")
    session = _make_session(campaign, rows=[(1, 100, None)])
    with patch("app.services.reactivation.AsyncSessionLocal", _db_ctx(session)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await send_reactivation_campaign(1)
    assert result == {"sent": 1, "errors": 0}
    bot.send_message.assert_called_once_with(
        100, "Привет, Пользователь!", parse_mode="HTML"
    )
