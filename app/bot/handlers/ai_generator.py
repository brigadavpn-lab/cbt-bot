import json
import logging
import google.generativeai as genai
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import Task

logger = logging.getLogger(__name__)
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
    !!! КРИТИЧЕСКИ ВАЖНЫЕ ТРЕБОВАНИЯ К ВАРИАНТАМ ("options"): !!!
    Текст в списке "options" должен быть ОЧЕНЬ КОРОТКИМ (максимум 2-3 слова или максимум ~30-40 символов).
    Не используй слэши и длинные перечисления (например, НЕ ПИШИ "Катастрофизация / Чтение мыслей").
    Выбирай одно конкретное название искажения.
    Иначе текст не влезет в кнопку бота.
    Варианты должны быть ТОЛЬКО названиями когнитивных искажений.
    (Примеры: "Чтение мыслей", "Катастрофизация", "Персонализация", "Долженствование", "Ярлыки").
    ЗАПРЕЩЕНО писать действия, советы или реакции (Например: НЕЛЬЗЯ писать "Позвонить другу" или "Решить проблему").
    !!! ТРЕБОВАНИЯ К РАЗНООБРАЗИЮ !!!
    1. ТЕМЫ: Чередуй самые разные жизненные сферы: отношения, быт, финансы, здоровье, воспитание детей, вождение, покупки, интернет, дружба, самооценка, хобби. Не зацикливайся только на работе.
    2. ИМЕНА: Используй максимально разнообразные имена. Не используй одни и те же подряд. Чередуй мужские и женские, обычные и редкие. Или пиши от первого лица ("Я...").
    3. ОБЪЕМ: Ситуация должна быть емкой, но понятной (2-4 предложения).
    4. ИСКАЖЕНИЯ: Не повторяй одни и те же искажения подряд. Старайся использовать разные искажения в каждом новом задании.
    !!! ТРЕБОВАНИЯ К СТИЛИСТИКЕ (ВАЖНО) !!!
    1. "Thought" (Мысль) должна звучать как ЖИВОЙ внутренний голос: эмоционально, резко, может содержать риторические вопросы или восклицания. Избегай сухого канцелярского языка.
    2. МАСШТАБ: Чередуй крупные проблемы с мелкими бытовыми неурядицами (не тот кофе, пробка, пятно на рубашке).

    !!! СПИСОК ИСКАЖЕНИЙ (ИСПОЛЬЗУЙ ТОЛЬКО ЭТИ ТЕРМИНЫ В ВАРИАНТАХ ОТВЕТА) !!!
    Для полей "correct_cognitive_distortion" и "options" используй СТРОГО названия из этого списка:
    1. Черно-белое мышление
    2. Чтение мыслей
    3. Сверхобобщение
    4. Катастрофизация
    5. Предсказания будущего
    6. Обесценивание
    7. Негативный фильтр
    8. Завышенные стандарты
    9. Тирания долженствования
    10. Магическое мышление
    11. Навешивание ярлыков
    12. Персонализация
    13. Обвинение
    14. Неадекватные социальные сравнения
    15. Ориентация на сожаление
    16. Эффект невозвратных затрат
    17. Ретроспективное искажение

    !!! ТЕМЫ-ТАБУ (КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО) !!!
    Никогда не генерируй ситуации, связанные с:
    1. Смертью, суицидом, желанием умереть.
    2. Онкологией, неизлечимыми болезнями.
    3. Самоповреждением (селфхарм).
    4. Физическим насилием, жестокостью.
    5. Сексуализированными домогательствами или насилием.
    Ситуации должны быть психологически безопасными (бытовыми, социальными, рабочими).

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

    except Exception:
        logger.exception("AI task generation failed")
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Попробовать ещё раз", callback_data="generate_new_task")
        builder.button(text="🔙 В меню", callback_data="back_to_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            "⚠️ Не удалось сгенерировать задачу. Попробуйте ещё раз через минуту.",
            reply_markup=builder.as_markup(),
        )