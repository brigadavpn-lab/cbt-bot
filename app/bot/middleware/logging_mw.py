import logging

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.states import UserState

logger = logging.getLogger("bot.actions")

TRUNCATE_LEN = 80


class LoggingMiddleware(BaseMiddleware):
    """
    Логирует каждое входящее сообщение и нажатие кнопки.
    Данные пишутся только в лог — пользователь ничего не видит.

    PII-safety:
    - text сообщения обрезается до TRUNCATE_LEN символов с суффиксом '…'
    - в FSM-состоянии UserState.waiting_for_situation реальный text заменяется
      на '<redacted: situation>', чтобы личные истории не попадали в stdout-логи
    """

    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user = event.from_user
            state: FSMContext | None = data.get("state")
            current_state = await state.get_state() if state else None
            if current_state == UserState.waiting_for_situation.state:
                text_repr = "<redacted: situation>"
            else:
                raw = event.text or ""
                text_repr = (raw[:TRUNCATE_LEN] + "…") if len(raw) > TRUNCATE_LEN else raw
            logger.info(
                "MSG | user_id=%s | text=%r",
                user.id if user else None,
                text_repr,
            )
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            logger.info(
                "BTN | user_id=%s | data=%r",
                user.id if user else None,
                event.data,
            )
        return await handler(event, data)
