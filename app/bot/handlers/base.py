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
        "Я — твой карманный психолог (CBT-Bot).\n"
        "Я помогу отловить негативные мысли.\n\n"
        "Выбери действие:"
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