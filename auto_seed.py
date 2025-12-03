import asyncio
import json
import google.generativeai as genai
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import Task

# --- НАСТРОЙКИ ---
BATCHES = 2         # Сколько раз спросить ИИ (2 раза)
TASKS_PER_BATCH = 5 # По 5 задач за раз
# Итого: 10 задач за один запуск. Хочешь больше - запусти скрипт несколько раз.

# Настраиваем ИИ
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    # Используем твою быструю модель
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    print("❌ Нет ключа API в настройках!")
    exit()

async def generate_and_save():
    print(f"🤖 Приступаю к генерации {BATCHES * TASKS_PER_BATCH} задач...")
    
    async with AsyncSessionLocal() as session:
        for i in range(BATCHES):
            print(f"⏳ Партия {i+1} из {BATCHES}...")
            
            prompt = f"""
            Придумай {TASKS_PER_BATCH} уникальных ситуаций для тренажера распознавания когнитивных искажений в когнитивно-поведенческой психотерапии.
            Темы: работа, отношения, страхи, самооценка, карьера, учеба, семья, дружба, успех, здоровье, деньги.

ВАЖНОЕ ТРЕБОВАНИЕ К ВАРИАНТАМ ОТВЕТОВ:
    Текст в списке "options" должен быть ОЧЕНЬ КОРОТКИМ (максимум 3-4 слова или максимум ~30-40 символов).
    Не используй слэши и длинные перечисления (например, НЕ ПИШИ "Катастрофизация / Чтение мыслей").
    Выбирай одно конкретное название искажения.
    Иначе текст не влезет в кнопку бота.
!!! КРИТИЧЕСКИ ВАЖНЫЕ ТРЕБОВАНИЯ К ВАРИАНТАМ ("options"): !!!
    1. Варианты должны быть ТОЛЬКО названиями когнитивных искажений.
       (Примеры: "Чтение мыслей", "Катастрофизация", "Персонализация", "Долженствование", "Ярлыки").
    2. ЗАПРЕЩЕНО писать действия, советы или реакции (Например: НЕЛЬЗЯ писать "Позвонить другу" или "Решить проблему").
            
            Верни ответ СТРОГО в формате JSON (список объектов).
            Структура:
            {{
                "situation": "Текст ситуации",
                "thought": "Негативная мысль",
                "correct_cognitive_distortion": "Название искажения (на русском)",
                "options": ["Правильный", "Неправильный1", "Неправильный2"],
                "explanation": "Краткое понятное обывателю пояснение"
            }}
            Никакого лишнего текста, только чистый JSON.
            """
            
            try:
                response = await model.generate_content_async(prompt)
                # Чистим ответ от возможных пометок кода
                text = response.text.replace("```json", "").replace("```", "").strip()
                
                tasks_data = json.loads(text)
                
                for task_json in tasks_data:
                    new_task = Task(
                        payload=task_json,
                        difficulty=1,
                        active=True
                    )
                    session.add(new_task)
                
                await session.commit()
                print(f"✅ Успешно добавлено: {len(tasks_data)} шт.")
                
            except Exception as e:
                print(f"⚠️ Ошибка в партии {i+1}: {e}")
                continue

    print("🎉 Готово! Задачи добавлены в базу.")

if __name__ == "__main__":
    asyncio.run(generate_and_save())