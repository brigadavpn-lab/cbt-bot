import logging
import secrets as py_secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from aiogram import Bot, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import settings
from app.bot.dispatcher import dp

# Настройка логирования (чтобы видеть ошибки в консоли)
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Создаем объект бота
bot = Bot(
    token=settings.BOT_TOKEN.get_secret_value(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Функция жизненного цикла: Что делать при включении/выключении
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- СТАРТ ---
    # Если указан WEBHOOK_URL, говорим Телеграму слать сообщения туда
    if settings.WEBHOOK_URL:
        webhook_endpoint = f"{settings.WEBHOOK_URL}/webhook"
        logger.info(f"Setting webhook to {webhook_endpoint}")
        await bot.set_webhook(
            url=webhook_endpoint,
            secret_token=settings.SECRET_TOKEN.get_secret_value(),
            drop_pending_updates=True
        )
    
    yield # Тут бот работает...
    
    # --- СТОП ---
    # При выключении удаляем вебхук
    if settings.WEBHOOK_URL:
        await bot.delete_webhook()
    await bot.session.close()

# Создаем приложение FastAPI (docs отключены в production)
app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

from app.admin.router import router as admin_router
app.include_router(admin_router)

# Адрес, куда стучится Телеграм
@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Проверка секретного токена от Telegram (timing-safe сравнение)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.SECRET_TOKEN.get_secret_value()
    if not py_secrets.compare_digest(secret, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Обработка сообщения
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    try:
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
    
    return {"status": "ok"}

# Простая проверка, жив ли сервер
@app.get("/health")
async def health_check():
    return {"status": "ok", "bot": "CBT_Trainer"}