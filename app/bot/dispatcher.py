import logging

from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers import (
    ai_generator,
    base,
    check_answer,
    my_situation,
    progress,
    test_mode,
    training,
)
from app.bot.middlewares.ai_quota import AiQuotaMiddleware
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.throttling import ThrottlingMiddleware
from app.bot.middlewares.user import UserMiddleware
from app.core.config import settings

logger = logging.getLogger(__name__)

if settings.REDIS_URL:
    storage = RedisStorage.from_url(settings.REDIS_URL)
else:
    storage = MemoryStorage()

dp = Dispatcher(storage=storage)

# Global: DB session + auto-create User. Order matters — DB must run before User.
db_mw = DbSessionMiddleware()
user_mw = UserMiddleware()
dp.message.middleware(db_mw)
dp.message.middleware(user_mw)
dp.callback_query.middleware(db_mw)
dp.callback_query.middleware(user_mw)

# Per-user throttling on AI-touching routers
ai_throttle = ThrottlingMiddleware(rate_seconds=1.5)
my_situation.router.message.middleware(ai_throttle)
my_situation.router.callback_query.middleware(ai_throttle)
ai_generator.router.callback_query.middleware(ai_throttle)

# Daily quota for AI requests (no-op if Redis is not configured)
ai_quota = AiQuotaMiddleware(redis_url=settings.REDIS_URL, daily_limit=settings.CLAUDE_DAILY_LIMIT)
my_situation.router.message.middleware(ai_quota)
ai_generator.router.callback_query.middleware(ai_quota)

# Order matters
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
