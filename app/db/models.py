from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)

    # Профиль
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)

    # Геймификация
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0, nullable=False)

    # Биллинг
    plan = Column(String, default="free", nullable=False)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    situation_requests_today = Column(Integer, default=0, nullable=False)
    generator_requests_today = Column(Integer, default=0, nullable=False)
    last_reset_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    payload = Column(JSON, nullable=False)
    difficulty = Column(Integer, default=1)
    active = Column(Boolean, default=True)


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    chosen_code = Column(String)
    is_correct = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentLog(Base):
    __tablename__ = "payment_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tg_id = Column(BigInteger, index=True, nullable=False)

    payment_method = Column(String, nullable=False)  # "stars" | "yukassa"
    plan_key = Column(String, nullable=False)  # "weekly" | "monthly"
    amount_rub = Column(Integer, nullable=True)
    amount_stars = Column(Integer, nullable=True)

    status = Column(String, default="pending", nullable=False)
    external_payment_id = Column(String, unique=True, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tg_id = Column(BigInteger, index=True, nullable=False)

    feature = Column(String, nullable=False)  # "situation" | "generator"
    model = Column(String, default="claude-sonnet-4-6", nullable=False)

    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cache_read_input_tokens = Column(Integer, default=0, nullable=False)
    cache_creation_input_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
