import logging
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task

logger = logging.getLogger(__name__)


async def _count_active(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Task.id)).where(Task.active.is_(True)))
    return int(result.scalar_one())


async def get_random_active_tasks(session: AsyncSession, n: int) -> list[Task]:
    """Returns up to n random active tasks using random offsets.

    Avoids `ORDER BY random()` on the whole table. For small N (1..10) this is
    a handful of cheap queries.
    """
    if n <= 0:
        return []

    total = await _count_active(session)
    if total == 0:
        return []

    sample_size = min(n, total)
    offsets = random.sample(range(total), sample_size)

    tasks: list[Task] = []
    for offset in offsets:
        result = await session.execute(
            select(Task).where(Task.active.is_(True)).order_by(Task.id).offset(offset).limit(1)
        )
        task = result.scalar_one_or_none()
        if task is not None:
            tasks.append(task)
    return tasks
