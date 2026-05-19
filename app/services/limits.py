from datetime import UTC, datetime

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User

FREE_LIMITS = {
    "situation": settings.FREE_LIMIT_SITUATION,
    "generator": settings.FREE_LIMIT_GENERATOR,
}

COUNTER_COL = {
    "situation": "situation_requests_today",
    "generator": "generator_requests_today",
}

FEATURE_LABEL = {
    "situation": "разборов ситуаций",
    "generator": "генераций задач",
}


def _aware(dt):
    """SQLite drops tzinfo from DateTime(timezone=True); re-tag as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def check_and_increment(session: AsyncSession, user: User, feature: str) -> dict:
    """Atomically checks the daily limit and increments the per-feature counter.

    Holds a row-level lock on the user row for the duration of the caller's
    transaction. Keep the surrounding transaction short — do NOT call Claude
    while holding this lock.

    Returns dict: {allowed, used, limit, remaining, plan}.
    """
    if feature not in FREE_LIMITS:
        raise ValueError(f"unknown feature: {feature}")

    # Re-fetch user with FOR UPDATE to serialize concurrent calls.
    locked = (
        await session.execute(select(User).where(User.id == user.id).with_for_update())
    ).scalar_one()

    now = datetime.now(UTC)
    today = now.date()

    # Auto-downgrade expired paid plan.
    expires = _aware(locked.plan_expires_at)
    if locked.plan == "paid" and (expires is None or expires <= now):
        locked.plan = "free"
        locked.plan_expires_at = None

    # Paid users skip the counter entirely.
    if locked.plan == "paid":
        return {
            "allowed": True,
            "used": 0,
            "limit": -1,
            "remaining": -1,
            "plan": "paid",
        }

    # Reset both counters on a new day.
    if locked.last_reset_date is None or locked.last_reset_date < today:
        locked.situation_requests_today = 0
        locked.generator_requests_today = 0
        locked.last_reset_date = today

    limit = FREE_LIMITS[feature]
    col = COUNTER_COL[feature]
    used = int(getattr(locked, col))

    if used >= limit:
        return {
            "allowed": False,
            "used": used,
            "limit": limit,
            "remaining": 0,
            "plan": "free",
        }

    setattr(locked, col, used + 1)

    return {
        "allowed": True,
        "used": used + 1,
        "limit": limit,
        "remaining": limit - used - 1,
        "plan": "free",
    }


def _paywall_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Оплатить Telegram Stars", callback_data="pay_stars")
    builder.button(text="💳 Оплатить картой (ЮКасса)", callback_data="pay_yukassa")
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def _paywall_text(feature: str, limit_info: dict) -> str:
    label = FEATURE_LABEL[feature]
    limit = limit_info["limit"]
    return (
        "⛔ <b>Дневной лимит исчерпан</b>\n\n"
        f"Сегодня вы уже использовали {limit} из {limit} бесплатных {label}.\n\n"
        "🔓 <b>Безлимитный доступ</b> открывает:\n"
        "• Неограниченный разбор ваших ситуаций\n"
        "• Неограниченную генерацию задач от ИИ\n\n"
        "Выберите способ оплаты:"
    )


async def show_paywall(
    target: types.Message | types.CallbackQuery,
    feature: str,
    limit_info: dict,
) -> None:
    text = _paywall_text(feature, limit_info)
    markup = _paywall_keyboard()

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=markup)
        except Exception:
            await target.message.answer(text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)
