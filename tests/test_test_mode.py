import pytest
from unittest.mock import AsyncMock, MagicMock

from app.bot.handlers.test_mode import finish_test, start_test_handler


USER_TG_ID = 12345  # matches conftest mock_message.chat.id and mock_callback.from_user.id


def _mock_settings(redis_url="redis://fake"):
    s = MagicMock()
    s.REDIS_URL = redis_url
    s.TEST_COOLDOWN_SECONDS = 86400
    s.TEST_SESSION_TTL = 3600
    return s


def _mock_db_session(user_xp=0):
    mock_user = MagicMock()
    mock_user.xp = user_xp

    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=mock_user)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session, mock_user


# ---------------------------------------------------------------------------
# T1 — first completion: XP awarded, cooldown key set in Redis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finish_test_awards_xp_and_sets_cooldown(
    fake_redis, mock_message, fsm_context, monkeypatch
):
    await fsm_context.update_data(
        task_ids=[1, 2, 3],
        current_index=3,
        correct_count=3,
        test_lock_token="test-token-abc",
    )

    session, mock_user = _mock_db_session(user_xp=0)
    monkeypatch.setattr("app.bot.handlers.test_mode.AsyncSessionLocal", lambda: session)
    monkeypatch.setattr("app.bot.handlers.test_mode.settings", _mock_settings())
    monkeypatch.setattr(
        "app.bot.handlers.test_mode.aioredis",
        MagicMock(from_url=lambda _: fake_redis),
    )

    await finish_test(mock_message, fsm_context)

    assert mock_user.xp == 80  # 50 base + 3 correct * 10
    assert await fake_redis.exists(f"test_cooldown:{USER_TG_ID}") == 1


# ---------------------------------------------------------------------------
# T2 — second attempt: blocked because cooldown key already exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_test_blocked_on_cooldown(
    fake_redis, mock_callback, fsm_context, monkeypatch
):
    await fake_redis.set(f"test_cooldown:{USER_TG_ID}", 1, ex=86400)

    mock_db_factory = MagicMock()
    monkeypatch.setattr("app.bot.handlers.test_mode.AsyncSessionLocal", mock_db_factory)
    monkeypatch.setattr("app.bot.handlers.test_mode.settings", _mock_settings())
    monkeypatch.setattr(
        "app.bot.handlers.test_mode.aioredis",
        MagicMock(from_url=lambda _: fake_redis),
    )

    await start_test_handler(mock_callback, fsm_context)

    mock_callback.answer.assert_awaited_once()
    args, kwargs = mock_callback.answer.call_args
    assert kwargs.get("show_alert") is True
    assert "24 часа" in args[0]
    mock_db_factory.assert_not_called()


# ---------------------------------------------------------------------------
# T3 — fail-closed: REDIS_URL not set → test blocked, error shown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_test_fail_closed_no_redis(
    mock_callback, fsm_context, monkeypatch
):
    mock_db_factory = MagicMock()
    monkeypatch.setattr("app.bot.handlers.test_mode.AsyncSessionLocal", mock_db_factory)
    monkeypatch.setattr("app.bot.handlers.test_mode.settings", _mock_settings(redis_url=None))

    await start_test_handler(mock_callback, fsm_context)

    mock_callback.answer.assert_awaited_once()
    args, kwargs = mock_callback.answer.call_args
    assert kwargs.get("show_alert") is True
    assert "недоступен" in args[0]
    mock_db_factory.assert_not_called()


# ---------------------------------------------------------------------------
# T4 — session lock: second concurrent start_test is blocked by SET NX
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_test_blocked_by_session_lock(
    fake_redis, mock_callback, fsm_context, monkeypatch
):
    await fake_redis.set(f"test_lock:{USER_TG_ID}", "other-token", nx=True, ex=3600)

    mock_db_factory = MagicMock()
    monkeypatch.setattr("app.bot.handlers.test_mode.AsyncSessionLocal", mock_db_factory)
    monkeypatch.setattr("app.bot.handlers.test_mode.settings", _mock_settings())
    monkeypatch.setattr(
        "app.bot.handlers.test_mode.aioredis",
        MagicMock(from_url=lambda _: fake_redis),
    )

    await start_test_handler(mock_callback, fsm_context)

    mock_callback.answer.assert_awaited_once()
    args, _ = mock_callback.answer.call_args
    assert "⏳" in args[0]
    mock_db_factory.assert_not_called()
