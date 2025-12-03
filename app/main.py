import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
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
    token=settings.BOT_TOKEN,
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
            secret_token=settings.SECRET_TOKEN,
            drop_pending_updates=True
        )
    
    yield # Тут бот работает...
    
    # --- СТОП ---
    # При выключении удаляем вебхук
    if settings.WEBHOOK_URL:
        await bot.delete_webhook()
    await bot.session.close()

# Создаем приложение FastAPI
app = FastAPI(lifespan=lifespan)

# Адрес, куда стучится Телеграм
@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Проверка "пароля" от Телеграма (защита от хакеров)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.SECRET_TOKEN:
        return status.HTTP_401_UNAUTHORIZED

    # Обработка сообщения
    data = await request.json()
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