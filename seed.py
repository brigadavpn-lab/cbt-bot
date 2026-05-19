import asyncio
import json
import logging

from sqlalchemy import select, text

from app.db.models import Task
from app.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_data() -> None:
    logger.info("🌱 Seeding tasks...")

    try:
        with open("seed_tasks.json", encoding="utf-8") as f:
            tasks_data = json.load(f)
    except FileNotFoundError:
        logger.error("❌ seed_tasks.json not found")
        return

    added = skipped = 0
    async with AsyncSessionLocal() as session:
        for task_info in tasks_data:
            situation = task_info["situation"]
            exists = await session.execute(
                select(Task.id).where(text("payload ->> 'situation' = :s")).params(s=situation)
            )
            if exists.scalar_one_or_none() is not None:
                skipped += 1
                continue

            session.add(
                Task(
                    payload={
                        "situation": situation,
                        "thought": task_info["thought"],
                        "correct_cognitive_distortion": task_info["correct_cognitive_distortion"],
                        "options": task_info["options"],
                        "explanation": task_info["explanation"],
                    },
                    difficulty=task_info["difficulty"],
                    active=True,
                )
            )
            added += 1

        await session.commit()

    logger.info("✅ Added: %d, skipped (already in DB): %d", added, skipped)


if __name__ == "__main__":
    asyncio.run(seed_data())
