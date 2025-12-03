from app.core.config import settings
import google.generativeai as genai

# 1. Берем ключ из настроек
print(f"🔑 Используем ключ: {settings.GEMINI_API_KEY[:5]}...")
genai.configure(api_key=settings.GEMINI_API_KEY)

print("\n--- СПРАШИВАЕМ GOOGLE О МОДЕЛЯХ ---")

try:
    # 2. Просим список всех моделей
    count = 0
    for m in genai.list_models():
        # Нас интересуют только те, которые умеют генерировать текст (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Доступна: {m.name}")
            count += 1
            
    if count == 0:
        print("❌ Список пуст. Возможно, проблема с правами доступа ключа.")

except Exception as e:
    print(f"❌ Ошибка при проверке: {e}")