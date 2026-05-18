import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.states import UserState
from app.core.config import settings
from app.services.claude import analyze_situation

logger = logging.getLogger(__name__)
router = Router()

MAX_INPUT_LEN = 4000


@router.callback_query(F.data == "my_situation")
async def start_my_situation(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_for_situation)

    text = (
        "🧠 <b>Разбор вашей ситуации</b>\n\n"
        "Опишите, что случилось, и какие мысли у вас возникли.\n"
        "<i>Пример: Начальник косо посмотрел, наверное, хочет меня уволить.</i>\n\n"
        "✍️ <b>Напишите вашу ситуацию ниже:</b>"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="back_to_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(UserState.waiting_for_situation)
async def process_situation(message: types.Message, state: FSMContext):
    if not settings.ANTHROPIC_API_KEY:
        await message.answer("⚠️ AI-ключ не настроен. Свяжитесь с администратором.")
        await state.clear()
        return

    user_text = (message.text or "").strip()
    if not user_text:
        await message.answer(
            "Пожалуйста, опишите ситуацию текстом — фото и стикеры я пока не понимаю."
        )
        return

    if len(user_text) > MAX_INPUT_LEN:
        await message.answer(f"Слишком длинное сообщение. Сократите до {MAX_INPUT_LEN} символов.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        ai_answer = await analyze_situation(user_text)
    except Exception:
        logger.exception("Claude API call failed")
        await message.answer("⚠️ Сервис временно недоступен. Попробуйте, пожалуйста, позже.")
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Разобрать другую ситуацию", callback_data="my_situation")
    builder.button(text="🔙 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await message.answer(ai_answer, reply_markup=builder.as_markup())
    await state.clear()
