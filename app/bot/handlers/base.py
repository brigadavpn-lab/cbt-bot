from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# Функция рисования меню (чтобы не дублировать код)
def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏋️ Тренировка", callback_data="start_training")
    builder.button(text="🎲 ИИ-Генератор задач", callback_data="generate_new_task")
    builder.button(text="📝 Тест (10 вопросов)", callback_data="start_test")
    builder.button(text="🧠 Своя ситуация", callback_data="my_situation")
    builder.button(text="📈 Мой прогресс", callback_data="my_progress")
    builder.adjust(1)
    return builder.as_markup()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    # Сбрасываем любые зависшие состояния (тесты, диалоги)
    await state.clear()
    
    text = (
        f"Привет, <b>{message.from_user.full_name}</b>! 👋\n\n"
        "Я — <b>CBT-Gym</b>, твой персональный тренажер по работе с автоматическими мыслями.\n"
        "Я помогаю находить когнитивные искажения — ошибки в мыслях, которые вызывают тревогу и стресс.\n\n"
        "💪 <b>Как мы будем тренироваться?</b>\n"
        "• <b>Генератор задач:</b> Решай уникальные кейсы от ИИ.\n"
        "• <b>Своя ситуация:</b> Расскажи проблему, и я помогу её разобрать.\n"
        "• <b>Прогресс:</b> Копи опыт (XP) и следи за серией побед!\n\n"
        "С чего начнем?"
    )
    await message.answer(text, reply_markup=get_main_menu())

# УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК КНОПКИ "НАЗАД"
@router.callback_query(F.data == "back_to_menu")
async def go_home(callback: types.CallbackQuery, state: FSMContext):
    # 1. Сбрасываем состояние (если пользователь был посреди теста)
    await state.clear()
    
    # 2. Меняем текст на главное меню
    text = "Вы вернулись в главное меню. Чем займемся?"
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()