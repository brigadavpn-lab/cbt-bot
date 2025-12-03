from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from app.core.config import settings
from app.bot.handlers import base, training, check_answer, progress, my_situation, test_mode, ai_generator

# ИМПОРТИРУЕМ ВСЕ НАШИ ХЭНДЛЕРЫ
from app.bot.handlers import base, training, check_answer, progress, my_situation

# Настройка памяти (Redis)
if settings.REDIS_URL:
    storage = RedisStorage.from_url(settings.REDIS_URL)
else:
    storage = MemoryStorage()

# Диспетчер
dp = Dispatcher(storage=storage)

# --- ПОДКЛЮЧАЕМ РОУТЕРЫ (ПОРЯДОК ВАЖЕН) ---
dp.include_router(base.router)          # 1. Меню /start
dp.include_router(training.router)      # 2. Выдача задач
dp.include_router(check_answer.router)  # 3. Проверка ответов
dp.include_router(progress.router)      # 4. Прогресс
dp.include_router(my_situation.router)  # 5. <-- НОВАЯ СТРОКА (Gemini)
dp.include_router(ai_generator.router) # <-- НОВАЯ СТРОКА
dp.include_router(test_mode.router)