import json
import logging
from anthropic import AsyncAnthropic
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import Task
from app.bot.states import GenState

logger = logging.getLogger(__name__)
router = Router()

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

GENERATOR_PROMPT = """
Придумай 1 ситуацию для тренировки выявления когнитивных искажений в когнитивно-поведенческой терапии (КПТ).

Верни ТОЛЬКО JSON. Никакого текста до и после. Не используй ```json или ``` — только чистый JSON.
Весь вывод — на русском языке.

ТРЕБОВАНИЯ К ВАРИАНТАМ ("options"):
- Ровно 4 варианта: 1 правильный + 3 неправильных.
- Текст каждого варианта — максимум 30–40 символов (только название искажения, без пояснений).
- Неправильные варианты — смежные по смыслу с правильным.
- Не используй искажения, явно не связанные с ситуацией.
- Перемешивай порядок: правильный не всегда первый.
- Запрещено писать действия или советы (например: "Позвонить другу").

ТРЕБОВАНИЯ К РАЗНООБРАЗИЮ:
1. Темы: отношения, быт, финансы, здоровье, воспитание детей, вождение, покупки, интернет, дружба, самооценка, хобби. Не зацикливайся на работе.
2. Имена: разнообразные, мужские и женские, обычные и редкие. Или от первого лица ("Я...").
3. Объём ситуации: 2–4 предложения.
4. Искажения: не повторяй одни и те же подряд.

ТРЕБОВАНИЯ К СТИЛИСТИКЕ:
1. "thought" — всегда от первого лица ("Я...") или с именем персонажа из ситуации. Живо, эмоционально, как реальный внутренний голос. Без канцелярита.
2. Масштаб: чередуй крупные проблемы с мелкими бытовыми (не тот кофе, пробка, пятно на рубашке).

СПИСОК ИСКАЖЕНИЙ — использовать ТОЛЬКО эти термины в полях "correct_cognitive_distortion" и "options":
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

ТЕМЫ-ТАБУ — категорически запрещено:
1. Смерть, суицид, желание умереть.
2. Онкология, неизлечимые болезни.
3. Самоповреждение (селфхарм).
4. Физическое насилие, жестокость.
5. Сексуализированные домогательства или насилие.
6. Политика
7. ЛГБТ-тематика

СТРУКТУРА JSON (строго):
{
    "situation": "2–4 предложения. Бытовая или социальная сцена.",
    "thought": "От первого лица или с именем. Живо и эмоционально.",
    "correct_cognitive_distortion": "Название из списка выше.",
    "options": ["Вариант1", "Вариант2", "Вариант3", "Вариант4"],
    "explanation": "Максимум 100 символов. Простым языком, без терминов КПТ."
}

ПРИМЕР ГОТОВОГО ОТВЕТА (строго такой формат):
{
    "situation": "Маша отправила другу голосовое сообщение, но он не ответил уже три часа. Обычно он отвечает быстро.",
    "thought": "Я точно его чем-то обидела. Он явно злится и не хочет со мной разговаривать.",
    "correct_cognitive_distortion": "Чтение мыслей",
    "options": ["Персонализация", "Чтение мыслей", "Катастрофизация", "Сверхобобщение"],
    "explanation": "Маша уверена, что знает причину молчания друга, хотя на самом деле он мог просто быть занят."
}
"""


@router.callback_query(F.data == "generate_new_task")
async def generate_task_handler(callback: types.CallbackQuery, state: FSMContext):
    if not settings.ANTHROPIC_API_KEY:
        await callback.answer("AI не настроен!", show_alert=True)
        return

    # 1. Просим подождать
    await callback.message.edit_text("🎲 <b>Придумываю ситуацию...</b>\nЭто займет пару секунд.")

    try:
        # 2. Запрос к Claude
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": GENERATOR_PROMPT}]
        )
        text = response.content[0].text.replace("```json", "").replace("```", "").strip()
        task_data = json.loads(text)

        # 3. Сохраняем в базу
        async with AsyncSessionLocal() as session:
            new_task = Task(payload=task_data, difficulty=1, active=True)
            session.add(new_task)
            await session.commit()
            await session.refresh(new_task)
            task_id = new_task.id

        # 4. Включаем состояние "Режим генератора" — это даст check_answer.py
        # показать кнопку "🎲 Сгенерировать ещё" вместо "Следующая задача"
        await state.set_state(GenState.active)

        # 5. Рисуем кнопки
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

    except json.JSONDecodeError:
        logger.exception("Claude returned invalid JSON for generator")
        await callback.message.edit_text(
            "⚠️ Ошибка: ИИ вернул неверный формат. Попробуй ещё раз.",
            reply_markup=InlineKeyboardBuilder().button(
                text="🎲 Попробовать снова", callback_data="generate_new_task"
            ).as_markup()
        )
    except Exception:
        logger.exception("Claude task generation failed")
        await callback.message.edit_text(
            "⚠️ Ошибка генерации. Попробуй ещё раз.",
            reply_markup=InlineKeyboardBuilder().button(
                text="🎲 Попробовать снова", callback_data="generate_new_task"
            ).as_markup()
        )
