import json
import google.generativeai as genai
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import Task

router = Router()

# Настраиваем модель
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash') 
else:
    model = None

@router.callback_query(F.data == "generate_new_task")
async def generate_task_handler(callback: types.CallbackQuery):
    if not model:
        await callback.answer("AI не настроен!", show_alert=True)
        return

    # 1. Просим подождать
    await callback.message.edit_text("🎲 <b>Придумываю ситуацию...</b>\nЭто займет пару секунд.")

    # 2. Промпт
    prompt = """
    Придумай 1 ситуацию для тренировки выявления когнитивных искажений в когнитивно-поведенческой терапии (КПТ).
    
    Верни ответ СТРОГО в формате JSON.
ВАЖНОЕ ТРЕБОВАНИЕ К ВАРИАНТАМ ОТВЕТОВ:
    Текст в списке "options" должен быть ОЧЕНЬ КОРОТКИМ (максимум 3-4 слова или максимум ~30-40 символов).
    Не используй слэши и длинные перечисления (например, НЕ ПИШИ "Катастрофизация / Чтение мыслей").
    Выбирай одно конкретное название искажения.
    Иначе текст не влезет в кнопку бота.
!!! КРИТИЧЕСКИ ВАЖНЫЕ ТРЕБОВАНИЯ К ВАРИАНТАМ ("options"): !!!
    1. Варианты должны быть ТОЛЬКО названиями когнитивных искажений.
       (Примеры: "Чтение мыслей", "Катастрофизация", "Персонализация", "Долженствование", "Ярлыки").
    2. ЗАПРЕЩЕНО писать действия, советы или реакции (Например: НЕЛЬЗЯ писать "Позвонить другу" или "Решить проблему").

    Структура JSON:
    {
        "situation": "Текст ситуации до 3-4 предложений.",
        "thought": "Автоматическая мысль с указанием персонажа, кто так думает, если того требует сама ситуация",
        "correct_cognitive_distortion": "Искажение (на русском)",
        "options": ["Правильный", "Неправильный1", "Неправильный2"],
        "explanation": "Краткое понятное обывателю пояснение"
    }
    """

    try:
        # 3. Запрос к ИИ
        response = await model.generate_content_async(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        task_data = json.loads(text)

        # 4. Сохраняем в базу (чтобы потом работала проверка ответа)
        async with AsyncSessionLocal() as session:
            new_task = Task(payload=task_data, difficulty=1, active=True)
            session.add(new_task)
            await session.commit()
            await session.refresh(new_task)
            task_id = new_task.id

       # 5. Рисуем кнопки
        builder = InlineKeyboardBuilder()
        
        # Сначала добавляем варианты ответов
        for index, option in enumerate(task_data["options"]):
            builder.button(text=option, callback_data=f"answer:{task_id}:{index}")
        
        # Потом добавляем кнопки управления
        builder.button(text="🎲 Сгенерировать новую", callback_data="generate_new_task")
        builder.button(text="🔙 В меню", callback_data="back_to_menu")
        
        # !!! ГЛАВНОЕ ИСПРАВЛЕНИЕ !!!
        # Цифра 1 в скобках означает: "Строго 1 кнопка в ряду"
        builder.adjust(1)

        msg_text = (
            f"✨ <b>Сгенерировано ИИ</b> ✨\n\n"
            f"<b>Ситуация:</b>\n{task_data['situation']}\n\n"
            f"<b>Мысль:</b>\n<i>«{task_data['thought']}»</i>\n\n"
            "🤔 <b>Что это за искажение?</b>"
        )

        await callback.message.edit_text(msg_text, reply_markup=builder.as_markup())

    except Exception as e:
        await callback.message.edit_text(f"⚠️ Ошибка генерации: {e}")