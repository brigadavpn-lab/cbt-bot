from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "CBT_Trainer"

    BOT_TOKEN: SecretStr
    ANTHROPIC_API_KEY: SecretStr
    ADMIN_TG_ID: int = 0

    SECRET_TOKEN: SecretStr

    DATABASE_URL: str
    REDIS_URL: str | None = None
    WEBHOOK_URL: str | None = None
    LOG_LEVEL: str = "INFO"

    ADMIN_LOGIN: str = "admin"
    ADMIN_PASSWORD: SecretStr

    AI_DAILY_LIMIT: int = 20
    AI_LOCK_TTL: int = 30
    MAX_SITUATION_LENGTH: int = 4000
    MONTHLY_SPEND_ALERT_USD: float = 25.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
