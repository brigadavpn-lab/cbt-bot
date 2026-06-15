from sqlalchemy import Column, Integer, String, Boolean, BigInteger, ForeignKey, JSON, DateTime, Text, UniqueConstraint
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
    max_streak = Column(Integer, default=0)  # рекорд в сериях
    
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Дата регистрации
    full_name = Column(String(512), nullable=True)                          # Имя из Telegram
    last_active_at = Column(DateTime(timezone=True), nullable=True)         # Последняя активность
    is_blocked = Column(Boolean, default=False, nullable=False)
    is_age_confirmed = Column(Boolean, default=False, nullable=False)

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


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    feature = Column(String(50), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReactivationCampaign(Base):
    __tablename__ = 'reactivation_campaigns'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    days_inactive = Column(Integer, nullable=False)
    message_text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    schedule_day = Column(String(10), nullable=True)    # mon/tue/wed/thu/fri/sat/sun
    schedule_hour = Column(Integer, nullable=True)      # 0-23 UTC
    schedule_minute = Column(Integer, nullable=True)    # 0-59
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ReactivationLog(Base):
    __tablename__ = 'reactivation_log'
    __table_args__ = (
        UniqueConstraint('campaign_id', 'user_id', name='uq_reactivation_campaign_user'),
    )

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('reactivation_campaigns.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=True, nullable=False)