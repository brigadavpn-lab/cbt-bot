from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Основные настройки ---
    APP_NAME: str = "CBT_Trainer"  # Имя нашего бота
    
    # --- Секреты (читаются из .env) ---
    # Мы указываем тип данных (str - строка).
    # Если переменной нет в .env, программа выдаст ошибку.
    BOT_TOKEN: str
    
    # Ключ Gemini может быть пустым (None), если мы его еще не получили
    GEMINI_API_KEY: str | None = None

    # --- Claude (Anthropic) ---
    ANTHROPIC_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 1024
    
    # Секретный токен для защиты вебхука
    SECRET_TOKEN: str = "my-secret-token"
    
    # --- Инфраструктура ---
    # Адрес базы данных
    DATABASE_URL: str
    # Адрес Redis (может быть пустым, если запускаем без него пока)
    REDIS_URL: str | None = None
    
    # --- Вебхук ---
    # Адрес, который дает Ngrok (заполним позже)
    WEBHOOK_URL: str | None = None
    
    # --- Логи ---
    LOG_LEVEL: str = "INFO"

    # Магическая настройка:
    # env_file=".env" -> говорит питону искать файл .env в главной папке
    # extra="ignore" -> если в .env есть лишние строки, просто игнорировать их
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Создаем единственный объект настроек, которым будем пользоваться везде
settings = Settings()