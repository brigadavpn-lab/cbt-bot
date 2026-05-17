import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import Task
from app.bot.states import GenState
from app.services.claude import generate_task

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "generate_new_task")
async def generate_task_handler(callback: types.CallbackQuery, state: FSMContext):
    if not settings.ANTHROPIC_API_KEY:
        await callback.answer("AI не настроен!", show_alert=True)
        return

    await callback.message.edit_text("🎲 <b>Придумываю ситуацию...</b>\nЭто займет пару секунд.")

    try:
        task_data = await generate_task()
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

    async with AsyncSessionLocal() as session:
        new_task = Task(payload=task_data, difficulty=1, active=True)
        session.add(new_task)
        await session.commit()
        await session.refresh(new_task)
        task_id = new_task.id

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
