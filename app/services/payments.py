import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import PaymentLog, User

logger = logging.getLogger(__name__)


def _aware(dt):
    """SQLite stores DateTime(timezone=True) as naive — re-tag as UTC for comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


PLANS: dict[str, dict] = {
    "weekly": {
        "label": "1 неделя",
        "days": 7,
        "stars": settings.PLAN_WEEKLY_STARS,
        "rub": settings.PLAN_WEEKLY_RUB,
    },
    "monthly": {
        "label": "1 месяц",
        "days": 30,
        "stars": settings.PLAN_MONTHLY_STARS,
        "rub": settings.PLAN_MONTHLY_RUB,
    },
}


def is_yukassa_configured() -> bool:
    return bool(
        settings.YUKASSA_SHOP_ID and settings.YUKASSA_SECRET_KEY and settings.PUBLIC_BASE_URL
    )


async def activate_plan(
    session: AsyncSession,
    *,
    user: User,
    plan_key: str,
    payment_method: str,
    external_payment_id: str | None,
    amount_rub: int | None = None,
    amount_stars: int | None = None,
) -> bool:
    """Idempotently activates a paid plan.

    Returns True if the plan was activated by THIS call, False if it was
    already activated by a previous (duplicate) webhook/payment.
    Does not commit — caller controls the transaction.
    """
    if plan_key not in PLANS:
        raise ValueError(f"unknown plan: {plan_key}")

    if external_payment_id is not None:
        existing = (
            await session.execute(
                select(PaymentLog).where(PaymentLog.external_payment_id == external_payment_id)
            )
        ).scalar_one_or_none()
        if existing is not None and existing.status == "succeeded":
            return False

    days = PLANS[plan_key]["days"]
    now = datetime.now(UTC)
    current_expiry = _aware(user.plan_expires_at)
    base = (
        current_expiry if (user.plan == "paid" and current_expiry and current_expiry > now) else now
    )
    user.plan = "paid"
    user.plan_expires_at = base + timedelta(days=days)

    session.add(
        PaymentLog(
            user_id=user.id,
            tg_id=user.tg_id,
            payment_method=payment_method,
            plan_key=plan_key,
            amount_rub=amount_rub,
            amount_stars=amount_stars,
            status="succeeded",
            external_payment_id=external_payment_id,
        )
    )

    return True


async def create_yukassa_payment(plan_key: str, tg_id: int) -> dict:
    """Creates a YooKassa payment. Runs the sync SDK call in a thread."""
    if plan_key not in PLANS:
        raise ValueError(f"unknown plan: {plan_key}")
    if not is_yukassa_configured():
        raise RuntimeError("YooKassa is not configured")

    from yookassa import Configuration, Payment

    Configuration.account_id = settings.YUKASSA_SHOP_ID
    Configuration.secret_key = settings.YUKASSA_SECRET_KEY

    amount = PLANS[plan_key]["rub"]
    label = PLANS[plan_key]["label"]
    return_url = settings.YUKASSA_RETURN_URL or f"{settings.PUBLIC_BASE_URL}/return"

    def _create():
        return Payment.create(
            {
                "amount": {"value": f"{amount}.00", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": f"CBT-Gym Pro {label}",
                "metadata": {"tg_id": str(tg_id), "plan": plan_key},
            },
            uuid.uuid4(),
        )

    payment = await asyncio.to_thread(_create)
    return {
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
    }


async def verify_yukassa_payment(payment_id: str) -> dict | None:
    """Re-fetches the payment from YooKassa to verify webhook authenticity.

    Returns dict {status, metadata, amount_rub} or None.
    """
    if not is_yukassa_configured():
        return None

    from yookassa import Configuration, Payment

    Configuration.account_id = settings.YUKASSA_SHOP_ID
    Configuration.secret_key = settings.YUKASSA_SECRET_KEY

    def _fetch():
        return Payment.find_one(payment_id)

    try:
        payment = await asyncio.to_thread(_fetch)
    except Exception:
        logger.exception("YooKassa payment lookup failed: %s", payment_id)
        return None

    try:
        amount_rub = int(payment.amount.value.split(".")[0])
    except Exception:
        amount_rub = None

    return {
        "status": payment.status,
        "metadata": dict(payment.metadata or {}),
        "amount_rub": amount_rub,
    }
