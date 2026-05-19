import logging

from aiogram import F, Router, types
from aiogram.types import LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaymentLog, User
from app.services.payments import (
    PLANS,
    activate_plan,
    create_yukassa_payment,
    is_yukassa_configured,
)

logger = logging.getLogger(__name__)
router = Router()


def _plans_keyboard(method: str):
    builder = InlineKeyboardBuilder()
    for key, info in PLANS.items():
        price = info["stars"] if method == "stars" else info["rub"]
        suffix = "⭐" if method == "stars" else "₽"
        builder.button(
            text=f"{info['label']} — {price} {suffix}",
            callback_data=f"pay_{method}:{key}",
        )
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "pay_stars")
async def pay_stars_menu(callback: types.CallbackQuery):
    text = "⭐ <b>Оплата через Telegram Stars</b>\n\n" "Выберите тариф:"
    await callback.message.edit_text(text, reply_markup=_plans_keyboard("stars"))
    await callback.answer()


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars_invoice(callback: types.CallbackQuery):
    plan_key = callback.data.split(":", 1)[1]
    if plan_key not in PLANS:
        await callback.answer("Неизвестный тариф", show_alert=True)
        return

    plan = PLANS[plan_key]
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"CBT-Gym Pro — {plan['label']}",
        description="Безлимитный доступ к ИИ-функциям бота.",
        payload=f"stars:{plan_key}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan["label"], amount=int(plan["stars"]))],
    )
    await callback.answer()


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_q: types.PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: types.Message, session: AsyncSession):
    sp = message.successful_payment
    parts = (sp.invoice_payload or "").split(":")
    if len(parts) < 3 or parts[0] != "stars":
        logger.warning("Unknown payment payload: %s", sp.invoice_payload)
        return

    plan_key = parts[1]
    if plan_key not in PLANS:
        logger.warning("Unknown plan in payment: %s", plan_key)
        return

    user = (
        await session.execute(select(User).where(User.tg_id == message.from_user.id))
    ).scalar_one()

    activated = await activate_plan(
        session,
        user=user,
        plan_key=plan_key,
        payment_method="stars",
        external_payment_id=sp.telegram_payment_charge_id,
        amount_stars=int(sp.total_amount),
    )
    # DbSessionMiddleware commits at the end.

    if activated:
        await message.answer(
            "✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Безлимитный доступ активирован до "
            f"{user.plan_expires_at.strftime('%d.%m.%Y')}."
        )
    else:
        await message.answer("Этот платёж уже был обработан ранее.")


@router.callback_query(F.data == "pay_yukassa")
async def pay_yukassa_menu(callback: types.CallbackQuery):
    if not is_yukassa_configured():
        await callback.answer(
            "Оплата картой временно недоступна. Попробуйте Stars.",
            show_alert=True,
        )
        return
    text = "💳 <b>Оплата картой через ЮКассу</b>\n\n" "Выберите тариф:"
    await callback.message.edit_text(text, reply_markup=_plans_keyboard("yukassa"))
    await callback.answer()


@router.callback_query(F.data.startswith("pay_yukassa:"))
async def pay_yukassa_link(callback: types.CallbackQuery, session: AsyncSession):
    plan_key = callback.data.split(":", 1)[1]
    if plan_key not in PLANS:
        await callback.answer("Неизвестный тариф", show_alert=True)
        return
    if not is_yukassa_configured():
        await callback.answer("ЮКасса не настроена", show_alert=True)
        return

    try:
        result = await create_yukassa_payment(plan_key, callback.from_user.id)
    except Exception:
        logger.exception("YooKassa payment creation failed")
        await callback.answer("Не удалось создать платёж. Попробуйте позже.", show_alert=True)
        return

    session.add(
        PaymentLog(
            user_id=None,
            tg_id=callback.from_user.id,
            payment_method="yukassa",
            plan_key=plan_key,
            amount_rub=PLANS[plan_key]["rub"],
            status="pending",
            external_payment_id=result["payment_id"],
        )
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Перейти к оплате", url=result["confirmation_url"])
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        f"Тариф <b>{PLANS[plan_key]['label']}</b> — {PLANS[plan_key]['rub']} ₽\n\n"
        "Нажмите кнопку ниже, чтобы оплатить. После успешной оплаты доступ "
        "активируется автоматически.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()
