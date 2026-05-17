from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.db.models import Task, User
from app.bot.states import TestState

router = Router()

# --- 1. ЗАПУСК ТЕСТА ---
@router.callback_query(F.data == "start_test")
async def start_test_handler(callback: types.CallbackQuery, state: FSMContext):
    # Берем 10 случайных задач из базы
    async with AsyncSessionLocal() as session:
        query = select(Task).order_by(func.random()).limit(10)
        result = await session.execute(query)
        tasks = result.scalars().all()

    # Если задач мало (мы только что почистили базу, но авто-сид должен был добавить 10-20)
    if len(tasks) < 5:
        await callback.answer("В базе мало задач! Сначала запустите генератор.", show_alert=True)
        return

    # Сохраняем ID задач в память бота (чтобы не потерять их в процессе теста)
    task_ids = [t.id for t in tasks]
    
    # Включаем состояние "В процессе теста"
    await state.set_state(TestState.in_progress)
    
    # Запоминаем начальные данные
    await state.update_data(task_ids=task_ids, current_index=0, correct_count=0)

    # Показываем первый вопрос (сессия выше уже закрыта — открываем новую внутри)
    await show_next_question(callback.message, state, None)
    await callback.answer()

# --- 2. ФУНКЦИЯ ПОКАЗА ВОПРОСА ---
async def show_next_question(message: types.Message, state: FSMContext, session):
    data = await state.get_data()
    index = data['current_index']
    task_ids = data['task_ids']

    # Если вопросы кончились -> идем на финиш
    if index >= len(task_ids):
        await finish_test(message, state)
        return

    current_task_id = task_ids[index]
    
    # Если сессия закрылась, открываем новую
    if session is None:
        async with AsyncSessionLocal() as new_session:
             task = await new_session.get(Task, current_task_id)
    else:
        task = await session.get(Task, current_task_id)
    
    # Рисуем кнопки ответов
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(task.payload['options']):
        # callback_data="test_ans:НОМЕР_ОТВЕТА"
        builder.button(text=option, callback_data=f"test_ans:{i}")
    
    # Кнопка прерывания теста (как ты просил)
    builder.button(text="🔙 В меню (прервать)", callback_data="back_to_menu")
    
    builder.adjust(1) # Кнопки в столбик

    progress_text = f"Вопрос {index + 1} из {len(task_ids)}"
    text = (
        f"📝 <b>{progress_text}</b>\n\n"
        f"<b>Ситуация:</b>\n{task.payload['situation']}\n\n"
        f"<i>{task.payload['thought']}</i>"
    )

    try:
        await message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup())

# --- 3. ОБРАБОТКА ОТВЕТА ---
@router.callback_query(TestState.in_progress, F.data.startswith("test_ans:"))
async def process_test_answer(callback: types.CallbackQuery, state: FSMContext):
    # Какой вариант выбрал пользователь?
    selected_index = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    current_index = data['current_index']
    task_ids = data['task_ids']
    correct_count = data['correct_count']

    # Проверяем ответ в базе
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_ids[current_index])
        correct_option = task.payload["correct_cognitive_distortion"]
        options = task.payload["options"]
        
        # Защита от выхода за границы массива (если вдруг опций меньше)
        if selected_index < len(options):
            selected_text = options[selected_index]
            
            if selected_text == correct_option:
                correct_count += 1
                await callback.answer("✅ Верно!")
            else:
                await callback.answer("❌ Ошибка!", show_alert=False)
        else:
            await callback.answer("⚠️ Ошибка данных", show_alert=False)

    # Обновляем счетчик и переходим к следующему вопросу
    await state.update_data(current_index=current_index + 1, correct_count=correct_count)
    await show_next_question(callback.message, state, None)

# --- 4. ФИНАЛ ТЕСТА ---
async def finish_test(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct = data['correct_count']
    total = len(data['task_ids'])
    
    # Очищаем состояние (выходим из режима теста)
    await state.clear()
    
    # Начисляем опыт (50 за прохождение + 10 за каждый верный)
    total_xp = 50 + (correct * 10)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == message.chat.id))
        user = result.scalar_one_or_none()
        if user:
            user.xp += total_xp
            # Увеличиваем счетчик завершенных серий, если нужно
            # user.streak += ... (тут сложнее, пока просто XP)
            await session.commit()

    # Оценка результата
    percent = (correct / total) * 100
    if percent == 100: grade = "🥇 Гроссмейстер КПТ!"
    elif percent >= 80: grade = "🥈 Отличный результат!"
    elif percent >= 50: grade = "🥉 Неплохо, но можно лучше."
    else: grade = "📉 Нужно больше тренироваться."

    # Кнопка выхода
    builder = InlineKeyboardBuilder()
    builder.button(text="🏁 В главное меню", callback_data="back_to_menu")

    text = (
        f"🏁 <b>Тест завершен!</b>\n\n"
        f"Результат: <b>{correct} из {total}</b>\n"
        f"{grade}\n\n"
        f"💰 Заработано: +{total_xp} XP"
    )
    
    await message.edit_text(text, reply_markup=builder.as_markup())