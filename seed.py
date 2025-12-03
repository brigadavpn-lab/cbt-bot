import asyncio
import json
import logging
from app.db.session import AsyncSessionLocal
from app.db.models import Task
from sqlalchemy import select

# Настраиваем простой вывод логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    logger.info("🌱 Начинаем посев данных (seeding)...")
    
    # 1. Открываем файл с задачами
    try:
        with open("seed_tasks.json", "r", encoding="utf-8") as f:
            tasks_data = json.load(f)
    except FileNotFoundError:
        logger.error("❌ Файл seed_tasks.json не найден!")
        return

    # 2. Подключаемся к базе
    async with AsyncSessionLocal() as session:
        count = 0
        for task_info in tasks_data:
            # Проверяем, есть ли уже такая задача (чтобы не дублировать при повторном запуске)
            # Мы используем SQL-запрос: "Найди задачу, у которой ситуация такая же..."
            # Нам нужно достать task_info["situation"] из JSON-поля payload
            
            # (Для простоты пока просто добавляем, если база пустая. 
            # В будущем можно усложнить проверку дубликатов).
            
            new_task = Task(
                payload={
                    "situation": task_info["situation"],
                    "thought": task_info["thought"],
                    "correct_cognitive_distortion": task_info["correct_cognitive_distortion"],
                    "options": task_info["options"],
                    "explanation": task_info["explanation"]
                },
                difficulty=task_info["difficulty"],
                active=True
            )
            
            session.add(new_task)
            count += 1
        
        # Сохраняем изменения
        await session.commit()
        logger.info(f"✅ Успешно добавлено задач: {count}")

if __name__ == "__main__":
    asyncio.run(seed_data())