from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, PaymentLog, User
from app.services.payments import activate_plan


@pytest.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _new_user(maker) -> int:
    async with maker() as s:
        u = User(tg_id=7777)
        s.add(u)
        await s.commit()
        return u.id


async def test_activate_plan_weekly(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        activated = await activate_plan(
            s,
            user=u,
            plan_key="weekly",
            payment_method="stars",
            external_payment_id="charge_1",
            amount_stars=150,
        )
        await s.commit()
        assert activated is True

    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        assert u.plan == "paid"
        assert u.plan_expires_at is not None
        # SQLite drops tzinfo — normalize both sides for comparison.
        expires = u.plan_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        assert expires > datetime.now(UTC) + timedelta(days=6)
        row = (await s.execute(select(PaymentLog))).scalar_one()
        assert row.status == "succeeded"
        assert row.amount_stars == 150


async def test_activate_plan_idempotent(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        await activate_plan(
            s,
            user=u,
            plan_key="monthly",
            payment_method="yukassa",
            external_payment_id="pay_abc",
            amount_rub=399,
        )
        await s.commit()

    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        first_expiry = u.plan_expires_at
        activated = await activate_plan(
            s,
            user=u,
            plan_key="monthly",
            payment_method="yukassa",
            external_payment_id="pay_abc",
            amount_rub=399,
        )
        await s.commit()
        assert activated is False  # duplicate webhook
        await s.refresh(u)
        assert u.plan_expires_at == first_expiry

    async with session_maker() as s:
        rows = (await s.execute(select(PaymentLog))).scalars().all()
        assert len(rows) == 1


async def test_activate_plan_extends_existing(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        await activate_plan(
            s,
            user=u,
            plan_key="weekly",
            payment_method="stars",
            external_payment_id="c1",
            amount_stars=150,
        )
        await s.commit()

    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        prev_expiry = u.plan_expires_at
        await activate_plan(
            s,
            user=u,
            plan_key="weekly",
            payment_method="stars",
            external_payment_id="c2",
            amount_stars=150,
        )
        await s.commit()
        await s.refresh(u)
        assert u.plan_expires_at > prev_expiry
        assert (u.plan_expires_at - prev_expiry).days == 7


async def test_unknown_plan_raises(session_maker):
    await _new_user(session_maker)
    async with session_maker() as s:
        u = (await s.execute(select(User))).scalar_one()
        with pytest.raises(ValueError):
            await activate_plan(
                s,
                user=u,
                plan_key="lifetime",
                payment_method="stars",
                external_payment_id=None,
            )
