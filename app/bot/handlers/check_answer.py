from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import AsyncSessionLocal
from app.db.models import Task, User, Attempt
from app.bot.states import GenState

router = Router()

@router.callback_query(F.data.startswith("answer:"))
async def answer_handler(callback: types.CallbackQuery, state: FSMContext):
    # Разбираем данные кнопки: "answer:ID_ЗАДАЧИ:НОМЕР_ОТВЕТА"
    _, task_id_str, option_index_str = callback.data.split(":")
    task_id = int(task_id_str)
    option_index = int(option_index_str)

    # FSM-проверка: task_id должен совпадать с тем, что выдан пользователю
    fsm_data = await state.get_data()
    if str(task_id) != str(fsm_data.get("current_task_id")):
        await callback.answer("Это задание уже не актуально.", show_alert=True)
        return
    if fsm_data.get("answer_accepted"):
        await callback.answer("Вы уже ответили на этот вопрос.", show_alert=True)
        return
    # Помечаем как принятый ДО обращения к БД (защита от параллельных нажатий)
    await state.update_data(answer_accepted=True)

    async with AsyncSessionLocal() as session:
        # 1. Ищем задачу
        task = await session.get(Task, task_id)
        if not task:
            await callback.answer("Ошибка: Задача не найдена.")
            return

        # 2. Проверяем правильность
        options = task.payload["options"]
        correct_option = task.payload["correct_cognitive_distortion"]
        explanation = task.payload["explanation"]
        
        # Защита от выхода за границы массива
        if option_index >= len(options):
            await callback.answer("Ошибка данных кнопки")
            return

        selected_text = options[option_index]
        is_correct = (selected_text == correct_option)

        # 3. Работаем с пользователем
        tg_id = callback.from_user.id
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(tg_id=tg_id, level=1, xp=0, streak=0, max_streak=0)
            session.add(user)
            await session.flush()

        # 4. Начисляем очки и серию
        if is_correct:
            user.xp += 10
            user.streak += 1
            
            # Проверяем рекорд (max_streak может быть None у старых юзеров, поэтому (user.max_streak or 0))
            current_max = user.max_streak if user.max_streak else 0
            if user.streak > current_max:
                user.max_streak = user.streak
            
            header = "✅ <b>Верно!</b>"
        else:
            user.streak = 0
            header = f"❌ <b>Ошибка.</b>\nПравильный ответ: <b>{correct_option}</b>"

        # 5. Сохраняем попытку
        attempt = Attempt(
            user_id=user.id,
            task_id=task.id,
            chosen_code=selected_text,
            is_correct=is_correct
        )
        try:
            session.add(attempt)
            await session.flush()
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await callback.answer("Вы уже ответили на этот вопрос.", show_alert=True)
            return

    # --- ЛОГИКА КНОПОК (ГЕНЕРАТОР или ТРЕНИРОВКА) ---
    builder = InlineKeyboardBuilder()
    
    # Узнаем, в каком режиме пользователь
    current_state = await state.get_state()
    
    if current_state == GenState.active:
        # Режим Генератора
        builder.button(text="🎲 Сгенерировать еще", callback_data="generate_new_task")
    else:
        # Режим Тренировки (обычный)
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