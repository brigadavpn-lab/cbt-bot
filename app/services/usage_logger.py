import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import UsageLog, User

# Claude Sonnet 4.x pricing (USD per 1M tokens), May 2026.
INPUT_PRICE_PER_M = 3.0
OUTPUT_PRICE_PER_M = 15.0
CACHE_READ_PRICE_PER_M = 0.30  # 90% off input
CACHE_WRITE_PRICE_PER_M = 3.75  # 1.25x input

stats_logger = logging.getLogger("usage_stats")


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


def calc_cost(u: Usage) -> float:
    return (
        u.input_tokens / 1_000_000 * INPUT_PRICE_PER_M
        + u.output_tokens / 1_000_000 * OUTPUT_PRICE_PER_M
        + u.cache_read_input_tokens / 1_000_000 * CACHE_READ_PRICE_PER_M
        + u.cache_creation_input_tokens / 1_000_000 * CACHE_WRITE_PRICE_PER_M
    )


async def log_usage(
    session: AsyncSession,
    *,
    tg_id: int,
    feature: str,
    usage: Usage,
) -> float:
    """Persists a UsageLog row and writes a flat line to usage.log.

    Does NOT commit — the caller manages the transaction.
    Returns calculated cost in USD.
    """
    cost = calc_cost(usage)

    user_id_result = await session.execute(select(User.id).where(User.tg_id == tg_id))
    user_id = user_id_result.scalar_one_or_none()

    entry = UsageLog(
        user_id=user_id,
        tg_id=tg_id,
        feature=feature,
        model=settings.CLAUDE_MODEL,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_input_tokens=usage.cache_read_input_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens,
        cost_usd=cost,
    )
    session.add(entry)

    stats_logger.info(
        "tg_id=%s | feature=%s | in=%s | out=%s | cache_r=%s | cache_w=%s | cost=$%.5f",
        tg_id,
        feature,
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_input_tokens,
        usage.cache_creation_input_tokens,
        cost,
    )

    return cost
