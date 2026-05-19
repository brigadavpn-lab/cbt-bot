from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import User

router = Router()

XP_PER_LEVEL = 100


@router.callback_query(F.data == "my_progress")
async def my_progress_handler(callback: types.CallbackQuery, user: User):
    xp_to_next = XP_PER_LEVEL - (user.xp % XP_PER_LEVEL)

    text = (
        f"👤 <b>Профиль:</b> {callback.from_user.full_name}\n\n"
        f"🏆 <b>Уровень:</b> {user.level}\n"
        f"⭐ <b>Очки (XP):</b> {user.xp}\n"
        f"🔥 <b>Серия побед:</b> {user.streak}\n"
        f"🏅 <b>Рекорд серии:</b> {user.max_streak}\n\n"
        f"<i>До следующего уровня: {xp_to_next} XP</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
