from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏋️ Тренировка", callback_data="start_training")
    builder.button(text="🎲 ИИ-Генератор задач", callback_data="generate_new_task")
    builder.button(text="📝 Тест (10 вопросов)", callback_data="start_test")
    builder.button(text="🧠 Своя ситуация", callback_data="my_situation")
    builder.button(text="📈 Мой прогресс", callback_data="my_progress")
    builder.adjust(1)
    return builder.as_markup()


WELCOME_TEXT = (
    "Привет, <b>{name}</b>! 👋\n\n"
    "Я — <b>CBT-Gym</b>, твой персональный тренажер по работе с автоматическими мыслями.\n"
    "Я помогаю находить когнитивные искажения — "
    "ошибки в мыслях, которые вызывают тревогу и стресс.\n\n"
    "💪 <b>Как мы будем тренироваться?</b>\n"
    "• <b>Генератор задач:</b> Решай уникальные кейсы от ИИ.\n"
    "• <b>Своя ситуация:</b> Расскажи проблему, и я помогу её разобрать.\n"
    "• <b>Прогресс:</b> Копи опыт (XP) и следи за серией побед!\n\n"
    "С чего начнем?"
)


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        WELCOME_TEXT.format(name=message.from_user.full_name),
        reply_markup=get_main_menu(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню. Чем займёмся?", reply_markup=get_main_menu())


@router.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Состояние сброшено. /menu — открыть меню.")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "<b>Команды:</b>\n"
        "/start — приветствие и меню\n"
        "/menu — главное меню\n"
        "/reset — сбросить текущий диалог/тест\n"
        "/help — это сообщение"
    )
    await message.answer(text)


@router.callback_query(F.data == "back_to_menu")
async def go_home(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Вы вернулись в главное меню. Чем займемся?",
        reply_markup=get_main_menu(),
    )
    await callback.answer()
