from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "CBT_Trainer"

    BOT_TOKEN: str
    ANTHROPIC_API_KEY: str
    ADMIN_TG_ID: int = 0

    SECRET_TOKEN: str = "my-secret-token"

    DATABASE_URL: str
    REDIS_URL: str | None = None
    WEBHOOK_URL: str | None = None
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
