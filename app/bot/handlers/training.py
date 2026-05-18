from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tasks import get_random_active_tasks

router = Router()


@router.callback_query(F.data == "start_training")
async def start_training_handler(callback: types.CallbackQuery, session: AsyncSession):
    tasks = await get_random_active_tasks(session, 1)
    if not tasks:
        await callback.message.answer("База задач пуста! Сначала запустите seed.py")
        await callback.answer()
        return
    task = tasks[0]

    task_data = task.payload
    builder = InlineKeyboardBuilder()
    for index, option_text in enumerate(task_data["options"]):
        builder.button(text=option_text, callback_data=f"answer:{task.id}:{index}")
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)

    text = (
        f"<b>Ситуация:</b>\n{task_data['situation']}\n\n"
        f"<b>Автоматическая мысль:</b>\n<i>«{task_data['thought']}»</i>\n\n"
        "🤔 <b>Какое это когнитивное искажение?</b>"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())

    await callback.answer()
