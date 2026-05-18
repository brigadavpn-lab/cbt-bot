from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.check_answer import _level_for_xp
from app.bot.states import TestState
from app.db.models import Task, User
from app.services.tasks import get_random_active_tasks

router = Router()


@router.callback_query(F.data == "start_test")
async def start_test_handler(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    tasks = await get_random_active_tasks(session, 10)
    if len(tasks) < 5:
        await callback.answer("В базе мало задач! Сначала запустите генератор.", show_alert=True)
        return

    task_ids = [t.id for t in tasks]
    await state.set_state(TestState.in_progress)
    await state.update_data(
        task_ids=task_ids,
        current_index=0,
        correct_count=0,
        tg_id=callback.from_user.id,
    )

    await _show_next_question(callback.message, state, session)
    await callback.answer()


async def _show_next_question(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    index = data["current_index"]
    task_ids = data["task_ids"]

    if index >= len(task_ids):
        await _finish_test(message, state, session)
        return

    task = await session.get(Task, task_ids[index])
    if task is None:
        await message.answer("⚠️ Задача исчезла, попробуйте начать тест заново.")
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    for i, option in enumerate(task.payload["options"]):
        builder.button(text=option, callback_data=f"test_ans:{i}")
    builder.button(text="🔙 В меню (прервать)", callback_data="back_to_menu")
    builder.adjust(1)

    text = (
        f"📝 <b>Вопрос {index + 1} из {len(task_ids)}</b>\n\n"
        f"<b>Ситуация:</b>\n{task.payload['situation']}\n\n"
        f"<i>{task.payload['thought']}</i>"
    )

    try:
        await message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(TestState.in_progress, F.data.startswith("test_ans:"))
async def process_test_answer(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    selected_index = int(callback.data.split(":")[1])

    data = await state.get_data()
    current_index = data["current_index"]
    task_ids = data["task_ids"]
    correct_count = data["correct_count"]

    task = await session.get(Task, task_ids[current_index])
    if task is not None:
        options = task.payload["options"]
        correct_option = task.payload["correct_cognitive_distortion"]
        if selected_index < len(options):
            if options[selected_index] == correct_option:
                correct_count += 1
                await callback.answer("✅ Верно!")
            else:
                await callback.answer("❌ Ошибка!", show_alert=False)
        else:
            await callback.answer("⚠️ Ошибка данных", show_alert=False)

    await state.update_data(current_index=current_index + 1, correct_count=correct_count)
    await _show_next_question(callback.message, state, session)


async def _finish_test(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    correct = data["correct_count"]
    total = len(data["task_ids"])
    tg_id = data.get("tg_id")

    await state.clear()

    total_xp = 50 + (correct * 10)

    if tg_id is not None:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.xp += total_xp
            user.level = _level_for_xp(user.xp)

    percent = (correct / total) * 100 if total else 0
    if percent == 100:
        grade = "🥇 Гроссмейстер КПТ!"
    elif percent >= 80:
        grade = "🥈 Отличный результат!"
    elif percent >= 50:
        grade = "🥉 Неплохо, но можно лучше."
    else:
        grade = "📉 Нужно больше тренироваться."

    builder = InlineKeyboardBuilder()
    builder.button(text="🏁 В главное меню", callback_data="back_to_menu")

    text = (
        f"🏁 <b>Тест завершен!</b>\n\n"
        f"Результат: <b>{correct} из {total}</b>\n"
        f"{grade}\n\n"
        f"💰 Заработано: +{total_xp} XP"
    )

    await message.edit_text(text, reply_markup=builder.as_markup())
