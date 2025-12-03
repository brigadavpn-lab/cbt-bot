from app.core.config import settings

print("--- ПРОВЕРКА НАСТРОЕК ---")
# Проверяем, не пустой ли токен
if settings.BOT_TOKEN:
    print("✅ Бот токен: ЗАГРУЖЕН")
    # Выведем первые 5 символов для верности
    print(f"   (Начало токена: {settings.BOT_TOKEN[:5]}...)")
else:
    print("❌ Бот токен: НЕ НАЙДЕН")

print(f"📂 База данных: {settings.DATABASE_URL}")
print("--- КОНЕЦ ПРОВЕРКИ ---")