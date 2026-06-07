from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.utils.html import esc

router = Router()

@router.callback_query(F.data == "my_progress")
async def my_progress_handler(callback: types.CallbackQuery):
    # 1. Ищем пользователя в базе по его Telegram ID
    tg_id = callback.from_user.id
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()

    # 2. Если пользователь еще не решал задачи, его может не быть в базе
    if not user:
        await callback.answer("Ты еще не решил ни одной задачи!", show_alert=True)
        return

    # 3. Формируем красивое сообщение
    # Рассчитываем уровень (например, каждые 100 очков - новый уровень)
    level = user.xp // 100 + 1
    xp_to_next = 100 - (user.xp % 100)

    text = (
        f"👤 <b>Профиль:</b> {esc(callback.from_user.full_name)}\n\n"
        f"🏆 <b>Уровень:</b> {level}\n"
        f"⭐ <b>Очки (XP):</b> {user.xp}\n"
        f"🔥 <b>Серия побед:</b> {user.streak}\n\n"
        f"<i>До следующего уровня осталось: {xp_to_next} XP</i>"
    )

    # 4. Кнопка "Назад", чтобы вернуться в меню
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

# Обработчик кнопки "Назад" (просто возвращает текст приветствия)
@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    # Копируем кнопки из стартового меню (чтобы не дублировать код, можно вынести отдельно, но пока так)
    builder = InlineKeyboardBuilder()
    builder.button(text="🏋️ Тренировка", callback_data="start_training")
    builder.button(text="📝 Тест (10 вопросов)", callback_data="start_test")
    builder.button(text="🧠 Своя ситуация", callback_data="my_situation")
    builder.button(text="📈 Мой прогресс", callback_data="my_progress")
    builder.adjust(1)

    text = (
        f"Привет, <b>{esc(callback.from_user.full_name)}</b>! 👋\n\n"
        "Я — твой карманный психолог.\n"
        "Выбери действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()