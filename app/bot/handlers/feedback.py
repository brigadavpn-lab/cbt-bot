import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.states import FeedbackState
from app.core.config import settings
from app.utils.html import esc

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "feedback")
async def start_feedback(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FeedbackState.waiting_for_message)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="back_to_menu")
    await callback.message.edit_text(
        "📝 <b>Обратная связь</b>\n\n"
        "Напишите ваше сообщение — оно будет отправлено администратору.\n\n"
        "<i>Чтобы отменить — нажмите кнопку ниже или напишите /cancel</i>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(FeedbackState.waiting_for_message)
async def process_feedback(message: types.Message, state: FSMContext):
    await state.clear()

    user = message.from_user
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username_str = f"@{esc(user.username)}" if user.username else "нет"

    admin_text = (
        "📩 <b>Новое сообщение от пользователя</b>\n\n"
        f"👤 <b>Имя:</b> {esc(user.full_name)}\n"
        f"🔗 <b>Username:</b> {username_str}\n"
        f"🆔 <b>ID:</b> {user.id}\n"
        f"🕐 <b>Время:</b> {timestamp}\n\n"
        f"💬 <b>Сообщение:</b>\n{esc(message.text)}"
    )

    if settings.ADMIN_TG_ID and settings.ADMIN_TG_ID != 0:
        try:
            await message.bot.send_message(
                chat_id=settings.ADMIN_TG_ID,
                text=admin_text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(
                "Failed to forward feedback to admin from user_id=%s error=%s",
                user.id,
                type(e).__name__,
            )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В главное меню", callback_data="back_to_menu")
    await message.answer(
        "✅ Ваше сообщение отправлено администратору. Спасибо за обратную связь!",
        reply_markup=builder.as_markup()
    )
