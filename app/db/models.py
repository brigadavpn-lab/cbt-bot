from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


# 1. Базовый класс
# Это как чистый лист бумаги. Все наши таблицы будут "наследоваться" от него.
class Base(DeclarativeBase):
    pass


# 2. Таблица пользователей
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)

    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 3. Таблица задач (CBT упражнения)
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)

    # В этом поле мы будем хранить весь текст задачи (ситуацию, варианты ответов)
    # JSON позволяет хранить сложные данные одной кучей
    payload = Column(JSON, nullable=False)

    difficulty = Column(Integer, default=1)  # Сложность (1 - легко, 3 - сложно)
    active = Column(Boolean, default=True)  # Активна ли задача (можно выключить, если она плохая)


# Таблица попыток (Кто какую задачу решал)
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))

    # ВОТ ЭТА СТРОКА ВАЖНА:
    chosen_code = Column(String)  # Какой ответ выбрал пользователь

    is_correct = Column(Boolean)  # Верно или нет
    created_at = Column(DateTime(timezone=True), server_default=func.now())
