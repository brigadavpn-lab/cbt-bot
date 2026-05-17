import logging

from aiogram import Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings
from app.bot.handlers import (
    base,
    training,
    check_answer,
    progress,
    my_situation,
    test_mode,
    ai_generator,
)
from app.bot.middlewares.throttling import ThrottlingMiddleware

logger = logging.getLogger(__name__)

if settings.REDIS_URL:
    storage = RedisStorage.from_url(settings.REDIS_URL)
else:
    storage = MemoryStorage()

dp = Dispatcher(storage=storage)

# Throttling только для AI-роутеров (дорогие вызовы)
ai_throttle = ThrottlingMiddleware(rate_seconds=1.5)
my_situation.router.message.middleware(ai_throttle)
my_situation.router.callback_query.middleware(ai_throttle)
ai_generator.router.callback_query.middleware(ai_throttle)

# Порядок важен
dp.include_router(base.router)
dp.include_router(training.router)
dp.include_router(check_answer.router)
dp.include_router(progress.router)
dp.include_router(my_situation.router)
dp.include_router(ai_generator.router)
dp.include_router(test_mode.router)


@dp.errors()
async def on_error(event: types.ErrorEvent):
    logger.exception("Unhandled update error", exc_info=event.exception)
    update = event.update
    target = None
    if update.message:
        target = update.message
    elif update.callback_query and update.callback_query.message:
        target = update.callback_query.message
    if target is not None:
        try:
            await target.answer("⚠️ Что-то пошло не так. Попробуйте ещё раз.")
        except Exception:
            pass
    return True
