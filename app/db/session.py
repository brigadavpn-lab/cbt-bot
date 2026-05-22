from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

# 1. Создаем "движок" (Engine)
# Это постоянный канал связи с базой данных по адресу из настроек.
# echo=False значит "не засоряй консоль лишними техническими деталями"
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 2. Фабрика сессий (SessionMaker)
# Каждый раз, когда нам нужно поработать с базой, мы просим эту фабрику
# выдать нам новую "сессию" (рабочее окно).
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# 3. Функция-помощник (Dependency)
# Мы будем использовать её в будущем, чтобы удобно получать доступ к базе
# внутри функций бота. Она сама откроет сессию и сама закроет её.
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session