import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, ErrorEvent

from app.bot.handlers import (
    ai_generator,
    base,
    broadcast,
    check_answer,
    my_situation,
    progress,
    test_mode,
    training,
)
from app.bot.middleware.logging_mw import LoggingMiddleware
from app.bot.middleware.rate_limit import RateLimitMiddleware
from app.core.config import settings

logger = logging.getLogger(__name__)

# Настройка памяти (Redis)
if settings.REDIS_URL:
    storage = RedisStorage.from_url(settings.REDIS_URL)
else:
    storage = MemoryStorage()

# Диспетчер
dp = Dispatcher(storage=storage)

# --- MIDDLEWARES ---
# Antispam: не более 10 сообщений в минуту от одного пользователя (только Message)
dp.message.middleware(RateLimitMiddleware(limit=10, period=60))

# Action-logging для отладки: MSG/BTN с PII-redact в FSM waiting_for_situation
logging_mw = LoggingMiddleware()
dp.message.middleware(logging_mw)
dp.callback_query.middleware(logging_mw)

# --- РОУТЕРЫ (ПОРЯДОК ВАЖЕН) ---
dp.include_router(base.router)          # 1. Меню /start, /cancel
dp.include_router(broadcast.router)    # 2. Рассылка (только для admin)
dp.include_router(training.router)     # 3. Выдача задач
dp.include_router(check_answer.router)  # 3. Проверка ответов
dp.include_router(progress.router)      # 4. Прогресс
dp.include_router(my_situation.router)  # 5. Своя ситуация (Claude)
dp.include_router(ai_generator.router)  # 6. Генератор задач (Claude)
dp.include_router(test_mode.router)     # 7. Режим теста


# --- STARTUP / SHUTDOWN: уведомление админа + регистрация команд ---
async def on_startup(bot: Bot):
    # Регистрируем команды в меню Telegram
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Запуск и приветствие"),
                BotCommand(command="cancel", description="Отменить текущее действие"),
            ]
        )
    except Exception:
        logger.exception("Failed to set bot commands")

    if settings.ADMIN_TG_ID:
        try:
            await bot.send_message(
                chat_id=settings.ADMIN_TG_ID,
                text="✅ <b>Бот запущен</b>\nCBT-Gym работает.",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to notify admin on startup")


async def on_shutdown(bot: Bot):
    if settings.ADMIN_TG_ID:
        try:
            await bot.send_message(
                chat_id=settings.ADMIN_TG_ID,
                text="⚠️ <b>Бот остановлен</b>",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to notify admin on shutdown")


dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ---
@dp.error()
async def global_error_handler(event: ErrorEvent):
    logger.error(
        "Необработанная ошибка: %s", event.exception, exc_info=event.exception
    )
    update = event.update
    target = None
    if update.message:
        target = update.message
    elif update.callback_query and update.callback_query.message:
        target = update.callback_query.message
    if target is not None:
        try:
            await target.answer(
                "⚠️ Произошла ошибка. Попробуйте ещё раз или напишите /start"
            )
        except Exception:
            pass
    return True
