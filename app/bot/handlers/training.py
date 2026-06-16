from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

# Наши инструменты для работы с базой
from app.db.session import AsyncSessionLocal
from app.db.models import Task

# Создаем новый роутер (главу для нашей книги команд)
router = Router()

# Этот декоратор говорит: "Срабатывай, когда нажата кнопка с data='start_training'"
@router.callback_query(F.data == "start_training")
async def start_training_handler(callback: types.CallbackQuery, state: FSMContext):
    # 1. Открываем соединение с базой
    async with AsyncSessionLocal() as session:
        # 2. Делаем запрос: "Дай мне 1 задачу, выбранную случайно"
        query = select(Task).order_by(func.random()).limit(1)
        result = await session.execute(query)
        task = result.scalar_one_or_none() # Получаем саму задачу или "пустоту"

    # 3. Если задач в базе нет (вдруг?)
    if not task:
        await callback.message.answer("База задач пуста! Сначала запустите seed.py")
        await callback.answer()
        return

    # 4. Формируем клавиатуру с вариантами ответов
    # Данные из базы лежат в task.payload (там наш JSON: situation, options...)
    task_data = task.payload

    # Сохраняем task_id в FSM для защиты от повторного ответа
    await state.clear()
    await state.update_data(current_task_id=task.id)

    builder = InlineKeyboardBuilder()

    # Создаем кнопки для каждого варианта ответа
    # В callback_data мы прячем ID задачи и номер ответа, чтобы потом проверить
    # Пример: answer:5:0 (Задача №5, Ответ №0)
    for index, option_text in enumerate(task_data["options"]):
        builder.button(
            text=option_text,
            callback_data=f"answer:{task.id}:{index}"
        )
# --- ДОБАВЛЕНА КНОПКА НАЗАД ---
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    # ------------------------------

    # Выстраиваем кнопки в столбик
    builder.adjust(1)

    # 5. Формируем текст сообщения
    text = (
        f"<b>Ситуация:</b>\n{task_data['situation']}\n\n"
        f"<b>Автоматическая мысль:</b>\n<i>«{task_data['thought']}»</i>\n\n"
        "🤔 <b>Какое это когнитивное искажение?</b>"
    )

    # 6. Отправляем сообщение
    # Мы используем edit_text, чтобы заменить меню на задачу (красивый переход)
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        # Если вдруг старое сообщение удалить нельзя, шлем новое
        await callback.message.answer(text, reply_markup=builder.as_markup())

    # Обязательно отвечаем телеграму, что кнопка сработала (чтобы часики не крутились)
    await callback.answer()