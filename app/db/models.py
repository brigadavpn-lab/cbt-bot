from sqlalchemy import Column, Integer, String, Boolean, BigInteger, ForeignKey, JSON, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase

# 1. Базовый класс
# Это как чистый лист бумаги. Все наши таблицы будут "наследоваться" от него.
class Base(DeclarativeBase):
    pass

# 2. Таблица пользователей
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)  # Внутренний номер в базе (1, 2, 3...)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False) # ID в Телеграме (длинный номер)
    
    # Геймификация
    level = Column(Integer, default=1)       # Уровень
    xp = Column(Integer, default=0)          # Опыт
    streak = Column(Integer, default=0)      # Серия побед без ошибок
    
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Дата регистрации

# 3. Таблица задач (CBT упражнения)
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    
    # В этом поле мы будем хранить весь текст задачи (ситуацию, варианты ответов)
    # JSON позволяет хранить сложные данные одной кучей
    payload = Column(JSON, nullable=False)
    
    difficulty = Column(Integer, default=1)  # Сложность (1 - легко, 3 - сложно)
    active = Column(Boolean, default=True)   # Активна ли задача (можно выключить, если она плохая)

# Таблица попыток (Кто какую задачу решал)
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    
    # ВОТ ЭТА СТРОКА ВАЖНА:
    chosen_code = Column(String) # Какой ответ выбрал пользователь
    
    is_correct = Column(Boolean) # Верно или нет
    created_at = Column(DateTime(timezone=True), server_default=func.now())