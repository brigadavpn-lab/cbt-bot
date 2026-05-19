from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, User
from app.services.limits import check_and_increment


@pytest.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _new_user(maker) -> User:
    async with maker() as s:
        u = User(tg_id=12345)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def test_free_situation_allows_5_blocks_6th(session_maker):
    await _new_user(session_maker)
    for i in range(5):
        async with session_maker() as s:
            u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
            res = await check_and_increment(s, u, "situation")
            await s.commit()
            assert res["allowed"] is True
            assert res["used"] == i + 1

    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        res = await check_and_increment(s, u, "situation")
        await s.commit()
        assert res["allowed"] is False
        assert res["remaining"] == 0


async def test_free_generator_limit_3(session_maker):
    await _new_user(session_maker)
    allowed_count = 0
    for _ in range(5):
        async with session_maker() as s:
            u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
            res = await check_and_increment(s, u, "generator")
            await s.commit()
            if res["allowed"]:
                allowed_count += 1
    assert allowed_count == 3


async def test_counters_reset_on_new_day(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        u.situation_requests_today = 5
        u.generator_requests_today = 3
        u.last_reset_date = (datetime.now(UTC) - timedelta(days=2)).date()
        await s.commit()

    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        res = await check_and_increment(s, u, "situation")
        await s.commit()
        assert res["allowed"] is True
        assert res["used"] == 1  # сброшено и инкрементировано


async def test_paid_plan_bypasses_limit(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        u.plan = "paid"
        u.plan_expires_at = datetime.now(UTC) + timedelta(days=10)
        u.situation_requests_today = 999
        await s.commit()

    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        res = await check_and_increment(s, u, "situation")
        await s.commit()
        assert res["allowed"] is True
        assert res["plan"] == "paid"


async def test_expired_paid_downgrades_to_free(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        u.plan = "paid"
        u.plan_expires_at = datetime.now(UTC) - timedelta(hours=1)
        await s.commit()

    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        res = await check_and_increment(s, u, "situation")
        await s.commit()
        assert res["plan"] == "free"

    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        assert u.plan == "free"
        assert u.plan_expires_at is None


async def test_unknown_feature_raises(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(__import__("sqlalchemy").select(User))).scalar_one()
        with pytest.raises(ValueError):
            await check_and_increment(s, u, "nonsense")
