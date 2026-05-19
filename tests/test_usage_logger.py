import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, UsageLog, User
from app.services.usage_logger import Usage, calc_cost, log_usage


def test_calc_cost_no_cache():
    u = Usage(input_tokens=1_000_000, output_tokens=500_000)
    assert calc_cost(u) == pytest.approx(3.0 + 7.5)


def test_calc_cost_with_cache():
    u = Usage(
        input_tokens=100_000,
        output_tokens=50_000,
        cache_read_input_tokens=900_000,
        cache_creation_input_tokens=200_000,
    )
    expected = (
        100_000 / 1_000_000 * 3.0
        + 50_000 / 1_000_000 * 15.0
        + 900_000 / 1_000_000 * 0.30
        + 200_000 / 1_000_000 * 3.75
    )
    assert calc_cost(u) == pytest.approx(expected)


async def test_log_usage_inserts_row():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as s:
            s.add(User(tg_id=42))
            await s.commit()

        async with maker() as s:
            cost = await log_usage(
                s,
                tg_id=42,
                feature="situation",
                usage=Usage(input_tokens=100, output_tokens=200),
            )
            await s.commit()

        assert cost > 0

        async with maker() as s:
            row = (await s.execute(select(UsageLog))).scalar_one()
            assert row.tg_id == 42
            assert row.feature == "situation"
            assert row.input_tokens == 100
            assert row.output_tokens == 200
            assert row.user_id is not None
    finally:
        await engine.dispose()


async def test_log_usage_without_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as s:
            await log_usage(
                s,
                tg_id=999,
                feature="generator",
                usage=Usage(input_tokens=1, output_tokens=1),
            )
            await s.commit()

        async with maker() as s:
            row = (await s.execute(select(UsageLog))).scalar_one()
            assert row.user_id is None
            assert row.tg_id == 999
    finally:
        await engine.dispose()
