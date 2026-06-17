import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# Must be set before any app.* import — Settings() instantiates at module level
# in app/core/config.py and requires these env vars to be present.
os.environ.setdefault("BOT_TOKEN", "test:fake_token")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-fake")
os.environ.setdefault("SECRET_TOKEN", "fake-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost/0")
os.environ.setdefault("ADMIN_TG_ID", "0")
os.environ.setdefault("MONTHLY_SPEND_ALERT_USD", "10.0")

# Pre-inject a mock for app.main to prevent its actual import.
# app.main creates a real Bot() at module level and pulls heavy Telegram deps.
# send_reactivation_campaign() does `from app.main import bot` lazily inside the
# function — that lazy import will resolve to this mock instead.
_mock_main = MagicMock()
_mock_main.bot = AsyncMock()
sys.modules["app.main"] = _mock_main

# ---------------------------------------------------------------------------
# Fixtures for integration tests
# ---------------------------------------------------------------------------

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
import fakeredis.aioredis


@pytest_asyncio.fixture
async def fsm_context():
    """Real FSMContext on MemoryStorage — not a mock, native aiogram mechanism."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=12345, user_id=12345)
    ctx = FSMContext(storage=storage, key=key)
    yield ctx
    await storage.close()


@pytest_asyncio.fixture
async def fake_redis():
    """FakeRedis with eval() support for Lua unlock script (requires lupa)."""
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server)
    yield client
    await client.aclose()


@pytest.fixture
def mock_session():
    """AsyncMock for AsyncSessionLocal — configure per test."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.fixture
def mock_callback():
    cb = AsyncMock()
    cb.from_user = MagicMock(id=12345)
    cb.message = AsyncMock()
    cb.data = "answer:1:0"
    return cb


@pytest.fixture
def mock_message():
    msg = AsyncMock()
    msg.from_user = MagicMock(id=12345)
    msg.chat = MagicMock(id=12345)
    msg.bot = AsyncMock()
    return msg
