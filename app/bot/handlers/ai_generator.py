import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.bot.states import GenState
from app.db.models import Task, User
from app.db.session import AsyncSessionLocal
from app.services.claude import generate_task
from app.services.limits import check_and_increment, show_paywall
from app.services.usage_logger import log_usage

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "generate_new_task")
async def generate_task_handler(callback: types.CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id

    # Quota check — short transaction.
    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if user is None:
            user = User(
                tg_id=tg_id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name,
            )
            s.add(user)
            await s.flush()
        limit_info = await check_and_increment(s, user, "generator")
        await s.commit()

    if not limit_info["allowed"]:
        await show_paywall(callback, "generator", limit_info)
        return

    await callback.message.edit_text("🎲 <b>Придумываю ситуацию...</b>\nЭто займет пару секунд.")

    try:
        task_data, usage = await generate_task()
    except Exception:
        logger.exception("Claude task generation failed")
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Попробовать ещё раз", callback_data="generate_new_task")
        builder.button(text="🔙 В меню", callback_data="back_to_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            "⚠️ Не удалось сгенерировать задачу. Попробуйте ещё раз через минуту.",
            reply_markup=builder.as_markup(),
        )
        return

    # Persist task + usage in a separate short transaction.
    async with AsyncSessionLocal() as s:
        new_task = Task(payload=task_data, difficulty=1, active=True)
        s.add(new_task)
        await s.flush()
        task_id = new_task.id
        try:
            await log_usage(s, tg_id=tg_id, feature="generator", usage=usage)
        except Exception:
            logger.exception("Failed to persist usage log")
        await s.commit()

    await state.set_state(GenState.active)

    builder = InlineKeyboardBuilder()
    for index, option in enumerate(task_data["options"]):
        builder.button(text=option, callback_data=f"answer:{task_id}:{index}")
    builder.button(text="🎲 Сгенерировать новую", callback_data="generate_new_task")
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)

    msg_text = (
        f"✨ <b>Сгенерировано ИИ</b> ✨\n\n"
        f"<b>Ситуация:</b>\n{task_data['situation']}\n\n"
        f"<b>Мысль:</b>\n<i>«{task_data['thought']}»</i>\n\n"
        "🤔 <b>Что это за искажение?</b>"
    )

    await callback.message.edit_text(msg_text, reply_markup=builder.as_markup())
