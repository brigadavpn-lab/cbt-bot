from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "CBT_Trainer"

    # --- Telegram ---
    BOT_TOKEN: str

    # --- Claude (Anthropic) ---
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 1024

    # --- Админ ---
    ADMIN_TG_ID: int

    # --- Биллинг (Freemium) ---
    FREE_LIMIT_SITUATION: int = 5
    FREE_LIMIT_GENERATOR: int = 3
    PLAN_WEEKLY_STARS: int = 150
    PLAN_WEEKLY_RUB: int = 149
    PLAN_MONTHLY_STARS: int = 390
    PLAN_MONTHLY_RUB: int = 399

    # --- YooKassa ---
    YUKASSA_SHOP_ID: str | None = None
    YUKASSA_SECRET_KEY: str | None = None
    PUBLIC_BASE_URL: str | None = None
    YUKASSA_RETURN_URL: str | None = None

    # --- HTTP server (aiohttp) ---
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000

    # --- Webhook Telegram (опционально) ---
    SECRET_TOKEN: str = "my-secret-token"
    WEBHOOK_URL: str | None = None

    # --- Инфраструктура ---
    DATABASE_URL: str
    REDIS_URL: str | None = None

    # --- Логи ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # text|json
    USAGE_LOG_FILE: str = "usage.log"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
