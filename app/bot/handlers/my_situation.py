import google.generativeai as genai
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.bot.states import UserState

router = Router()

# Настраиваем Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    model = None

# --- ЭТАП 1: Кнопка нажата ---
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

# --- ЭТАП 2: Обработка текста ---
@router.message(UserState.waiting_for_situation)
async def process_situation(message: types.Message, state: FSMContext):
    if not model:
        await message.answer("⚠️ Ошибка: AI-ключ не настроен.")
        await state.clear()
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    user_text = message.text
    
    # --- ПРОМПТ (Используем тройные кавычки!) ---
    prompt = f"""
    Ты — опытный психолог, специалист по когнитивно-поведенческой терапии (КПТ).
    Твоя задача — проанализировать ситуацию пользователя: "{user_text}"

    !!! СПИСОК ИСКАЖЕНИЙ (Используй термины строго отсюда) !!!
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

    Сделай разбор в формате:
    1. 🧐 <b>Когнитивное искажение:</b> (Назови одно или несколько из списка выше)
    2. 🧠 <b>Почему это ошибка:</b> (Краткое объяснение)
    3. 💡 <b>Рациональный ответ:</b> (Как стоит думать, чтобы снизить тревогу)

    Отвечай эмпатично, с поддержкой. Используй эмодзи.
    """

    try:
        response = await model.generate_content_async(prompt)
        ai_answer = response.text
        
        # Кнопки
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Разобрать другую ситуацию", callback_data="my_situation")
        builder.button(text="🔙 В главное меню", callback_data="back_to_menu")
        builder.adjust(1)

        await message.answer(ai_answer, reply_markup=builder.as_markup())
        
    except Exception as e:
        await message.answer(f"Произошла ошибка при связи с ИИ: {e}")
    
    await state.clear()