import os
import sys
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
