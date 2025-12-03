from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext # <--- Важный импорт
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import Task, User, Attempt
from app.bot.states import GenState # <--- Важный импорт

router = Router()

# Добавили state: FSMContext
@router.callback_query(F.data.startswith("answer:"))
async def answer_handler(callback: types.CallbackQuery, state: FSMContext):
    # Разбираем данные кнопки
    _, task_id_str, option_index_str = callback.data.split(":")
    task_id = int(task_id_str)
    option_index = int(option_index_str)

    async with AsyncSessionLocal() as session:
        # 1. Проверяем задачу и ответ
        task = await session.get(Task, task_id)
        if not task:
            await callback.answer("Ошибка: Задача не найдена.")
            return

        options = task.payload["options"]
        correct_option = task.payload["correct_cognitive_distortion"]
        explanation = task.payload["explanation"]
        
        selected_text = options[option_index]
        is_correct = (selected_text == correct_option)

        # 2. Обновляем статистику пользователя
        tg_id = callback.from_user.id
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(tg_id=tg_id, level=1, xp=0, streak=0)
            session.add(user)
            await session.flush()

        if is_correct:
            user.xp += 10
            user.streak += 1
            header = "✅ <b>Верно!</b>"
        else:
            user.streak = 0
            header = f"❌ <b>Ошибка.</b>\nПравильный ответ: <b>{correct_option}</b>"

        # 3. Сохраняем попытку
        attempt = Attempt(
            user_id=user.id,
            task_id=task.id,
            chosen_code=selected_text,
            is_correct=is_correct
        )
        session.add(attempt)
        await session.commit()

    # --- 4. САМОЕ ГЛАВНОЕ: ВЫБОР КНОПОК ---
    builder = InlineKeyboardBuilder()
    
    # Спрашиваем у бота: "В каком мы сейчас состоянии?"
    current_state = await state.get_state()
    
    if current_state == GenState.active:
        # Если включен режим Генератора
        builder.button(text="🎲 Сгенерировать еще", callback_data="generate_new_task")
    else:
        # Если режим обычный (Тренировка)
        builder.button(text="➡️ Следующая задача", callback_data="start_training")

    # Кнопка выхода нужна всегда
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    
    builder.adjust(1)
    
    text = (
        f"{header}\n\n"
        f"📖 <b>Пояснение:</b>\n{explanation}\n\n"
        f"🏆 Твой опыт: {user.xp} XP | Серия: {user.streak} 🔥"
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()