import logging

from anthropic import AsyncAnthropic
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.bot.states import UserState

logger = logging.getLogger(__name__)
router = Router()

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

SITUATION_SYSTEM_PROMPT = """
Ты — опытный психолог, специалист по когнитивно-поведенческой терапии (КПТ).
Твоя задача — проанализировать ситуацию пользователя и помочь выявить когнитивные искажения.

Используй ТОЛЬКО термины из этого списка:
1. Черно-белое мышление
2. Чтение мыслей
3. Сверхобобщение
4. Катастрофизация
5. Предсказания будущего
6. Обесценивание
7. Негативный фильтр
8. Завышенные стандарты
9. Тирания долженствования
10. Магическое мышление
11. Навешивание ярлыков
12. Персонализация
13. Обвинение
14. Неадекватные социальные сравнения
15. Ориентация на сожаление
16. Эффект невозвратных затрат
17. Ретроспективное искажение

Формат ответа строго:
1. 🧐 <b>Когнитивное искажение:</b> [название из списка]
2. 🧠 <b>Почему это ошибка:</b> [краткое объяснение]
3. 💡 <b>Рациональный ответ:</b> [как стоит думать]

Отвечай эмпатично, с поддержкой. Используй эмодзи. Отвечай на русском языке.
""".strip()


@router.callback_query(F.data == "my_situation")
async def start_my_situation(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_for_situation)

    text = (
        "🧠 <b>Разбор вашей ситуации</b>\n\n"
        "Опишите, что случилось, и какие мысли у вас возникли.\n"
        "<i>Пример: Начальник косо посмотрел, наверное, хочет меня уволить.</i>\n\n"
        "✍️ <b>Напишите вашу ситуацию ниже:</b>\n\n"
        "<i>Чтобы отменить — напишите /cancel</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="back_to_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(UserState.waiting_for_situation)
async def process_situation(message: types.Message, state: FSMContext):
    if not settings.ANTHROPIC_API_KEY:
        await message.answer("⚠️ Ошибка: AI-ключ не настроен.")
        await state.clear()
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    user_text = message.text

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SITUATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}]
        )
        ai_answer = response.content[0].text

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Разобрать другую ситуацию", callback_data="my_situation")
        builder.button(text="🔙 В главное меню", callback_data="back_to_menu")
        builder.adjust(1)

        await message.answer(ai_answer, reply_markup=builder.as_markup())

    except Exception:
        logger.exception("Claude API call failed (analyze_situation)")
        await message.answer("⚠️ Произошла ошибка при связи с ИИ. Попробуйте позже.")

    await state.clear()
