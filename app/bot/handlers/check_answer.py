from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import GenState
from app.db.models import Attempt, Task, User

router = Router()

XP_PER_CORRECT = 10
XP_PER_LEVEL = 100


def _level_for_xp(xp: int) -> int:
    return xp // XP_PER_LEVEL + 1


@router.callback_query(F.data.startswith("answer:"))
async def answer_handler(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
):
    _, task_id_str, option_index_str = callback.data.split(":")
    task_id = int(task_id_str)
    option_index = int(option_index_str)

    task = await session.get(Task, task_id)
    if task is None:
        await callback.answer("Ошибка: задача не найдена.")
        return

    options = task.payload["options"]
    correct_option = task.payload["correct_cognitive_distortion"]
    explanation = task.payload["explanation"]

    if option_index >= len(options):
        await callback.answer("Ошибка данных кнопки")
        return

    selected_text = options[option_index]
    is_correct = selected_text == correct_option

    if is_correct:
        user.xp += XP_PER_CORRECT
        user.streak += 1
        if user.streak > user.max_streak:
            user.max_streak = user.streak
        header = "✅ <b>Верно!</b>"
    else:
        user.streak = 0
        header = f"❌ <b>Ошибка.</b>\nПравильный ответ: <b>{correct_option}</b>"

    user.level = _level_for_xp(user.xp)

    session.add(
        Attempt(
            user_id=user.id,
            task_id=task.id,
            chosen_code=selected_text,
            is_correct=is_correct,
        )
    )

    builder = InlineKeyboardBuilder()
    current_state = await state.get_state()
    if current_state == GenState.active.state:
        builder.button(text="🎲 Сгенерировать еще", callback_data="generate_new_task")
        await state.clear()
    else:
        builder.button(text="➡️ Следующая задача", callback_data="start_training")
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)

    text = (
        f"{header}\n\n"
        f"📖 <b>Пояснение:</b>\n{explanation}\n\n"
        f"🏆 Твой опыт: {user.xp} XP | Серия: {user.streak} 🔥"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())

    await callback.answer()
