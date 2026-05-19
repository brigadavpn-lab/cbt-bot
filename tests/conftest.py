import os

# Provide required settings before app.core.config is imported anywhere.
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ADMIN_TG_ID", "111111")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("USAGE_LOG_FILE", "/tmp/usage_test.log")
