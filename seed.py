import asyncio
import json
import logging
from app.db.session import AsyncSessionLocal
from app.db.models import Task
from app.schemas.task_schema import GeneratedTaskSchema
from pydantic import ValidationError
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    logger.info("🌱 Начинаем посев данных (seeding)...")

    try:
        with open("seed_tasks.json", "r", encoding="utf-8") as f:
            tasks_data = json.load(f)
    except FileNotFoundError:
        logger.error("❌ Файл seed_tasks.json не найден!")
        return

    async with AsyncSessionLocal() as session:
        count = 0
        skipped = 0
        for task_info in tasks_data:
            try:
                payload_fields = {k: v for k, v in task_info.items() if k in GeneratedTaskSchema.model_fields}
                validated = GeneratedTaskSchema(**payload_fields)
            except ValidationError as e:
                logger.error("Validation failed for task '%s': %s", task_info.get("situation", "")[:50], e)
                continue

            existing = await session.execute(
                select(Task).where(
                    Task.payload["situation"].astext == task_info["situation"]
                )
            )
            if existing.scalar_one_or_none():
                logger.info("Skipping duplicate task: %s", task_info["situation"][:50])
                skipped += 1
                continue

            new_task = Task(
                payload=validated.model_dump(),
                difficulty=task_info.get("difficulty", 1),
                active=True,
            )
            session.add(new_task)
            count += 1

        await session.commit()
        logger.info("✅ Успешно добавлено задач: %d (пропущено дублей: %d)", count, skipped)

if __name__ == "__main__":
    asyncio.run(seed_data())
