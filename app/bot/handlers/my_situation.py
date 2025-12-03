import google.generativeai as genai
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.bot.states import UserState

router = Router()

# 1. Настраиваем Gemini (если ключ есть)
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash') # Используем быструю модель
else:
    model = None

# --- ЭТАП 1: Пользователь нажал кнопку "Своя ситуация" ---
@router.callback_query(F.data == "my_situation")
async def start_my_situation(callback: types.CallbackQuery, state: FSMContext):
    # Переводим бота в режим ожидания
    await state.set_state(UserState.waiting_for_situation)
    
    text = (
        "🧠 <b>Разбор вашей ситуации</b>\n\n"
        "Опишите, что случилось, и какие мысли у вас возникли.\n"
        "<i>Пример: Начальник косо посмотрел, наверное, хочет меня уволить.</i>\n\n"
        "✍️ <b>Напишите вашу ситуацию ниже:</b>"
    )
    # Кнопка отмены, если передумал
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="back_to_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

# --- ЭТАП 2: Пользователь прислал текст ---
@router.message(UserState.waiting_for_situation)
async def process_situation(message: types.Message, state: FSMContext):
    # Проверка: Есть ли ключ?
    if not model:
        await message.answer("⚠️ Ошибка: AI-ключ не настроен. Обратитесь к админу.")
        await state.clear()
        return

    # Сообщаем, что бот "печатает" (чтобы пользователь не скучал)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    user_text = message.text
    
    # --- ПРОМПТ (Инструкция для ИИ) ---
    prompt = (
        f"Ты — опытный клинический психолог, крупный специалист по когнитивно-поведенческой терапии (КПТ). "
        f"Твоя задача — проанализировать ситуацию пользователя.\n\n"
        f"Ситуация пользователя: \"{user_text}\"\n\n"
        f"Сделай разбор в таком формате:\n"
        f"1. 🧐 <b>Когнитивное искажение:</b> (Определи, какое или какие именно, например: Чтение мыслей, Катастрофизация и т.д.)\n"
        f"2. 🧠 <b>Почему это когнитивное искажение:</b> (Подробно объясни используя понятные примеры из жизни)\n"
        f"3. 💡 <b>Рациональный ответ:</b> (Как можно было бы думать в этой ситуации иначе)\n\n"
        f"Отвечай эмпатично и бережно, соблюдая этику, с объяснениями и по делу. Используй эмодзи."
    )

    try:
        # Отправляем запрос в Google
        response = await model.generate_content_async(prompt)
        ai_answer = response.text
        
        # Добавляем кнопку "Меню"
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 В главное меню", callback_data="back_to_menu")

        # Отправляем ответ
        await message.answer(ai_answer, reply_markup=builder.as_markup())
        
    except Exception as e:
        await message.answer(f"Произошла ошибка при связи с ИИ: {e}")
    
    # Выходим из режима ожидания
    await state.clear()