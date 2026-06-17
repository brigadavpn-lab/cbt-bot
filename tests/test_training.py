import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import IntegrityError

from app.bot.handlers.check_answer import answer_handler


TASK_PAYLOAD = {
    "options": ["Катастрофизация", "Черно-белое мышление", "Персонализация"],
    "correct_cognitive_distortion": "Катастрофизация",
    "explanation": "Это катастрофизация потому что...",
}


def _make_mock_session(flush_side_effect=None):
    """Build a properly configured async context-manager session mock."""
    mock_task = MagicMock()
    mock_task.id = 1
    mock_task.payload = TASK_PAYLOAD

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.xp = 0
    mock_user.streak = 0
    mock_user.max_streak = 0

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=mock_user)

    session = AsyncMock()
    session.get = AsyncMock(return_value=mock_task)
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock(side_effect=flush_side_effect)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session, mock_user


# ---------------------------------------------------------------------------
# T1 — normal flow: correct answer, Attempt saved, user sees result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_handler_correct_answer(mock_callback, fsm_context, monkeypatch):
    await fsm_context.update_data(current_task_id=1)
    mock_callback.data = "answer:1:0"  # index 0 = "Катастрофизация" = correct

    session, mock_user = _make_mock_session()
    monkeypatch.setattr("app.bot.handlers.check_answer.AsyncSessionLocal", lambda: session)

    await answer_handler(mock_callback, fsm_context)

    session.add.assert_called_once()
    session.commit.assert_awaited_once()

    result_text = mock_callback.message.edit_text.call_args[0][0]
    assert "✅" in result_text and "Верно" in result_text
    assert "🏆" in result_text


# ---------------------------------------------------------------------------
# T2 — stale FSM: task_id mismatch → "не актуально", DB factory never opened
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_handler_stale_fsm(mock_callback, fsm_context, monkeypatch):
    await fsm_context.update_data(current_task_id=99)  # different task
    mock_callback.data = "answer:1:0"

    mock_session_factory = MagicMock()
    monkeypatch.setattr(
        "app.bot.handlers.check_answer.AsyncSessionLocal",
        mock_session_factory,
    )

    await answer_handler(mock_callback, fsm_context)

    mock_callback.answer.assert_awaited_once_with(
        "Это задание уже не актуально.", show_alert=True
    )
    mock_session_factory.assert_not_called()


# ---------------------------------------------------------------------------
# T3 — race condition: IntegrityError on flush → rollback + "уже отвечал"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_handler_integrity_error(mock_callback, fsm_context, monkeypatch):
    await fsm_context.update_data(current_task_id=1)
    mock_callback.data = "answer:1:0"

    session, _ = _make_mock_session(flush_side_effect=IntegrityError(None, None, None))
    monkeypatch.setattr("app.bot.handlers.check_answer.AsyncSessionLocal", lambda: session)

    await answer_handler(mock_callback, fsm_context)

    session.rollback.assert_awaited_once()
    mock_callback.answer.assert_awaited_with("Ты уже отвечал на этот вопрос.", show_alert=True)
    session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# T4 — order: edit_reply_markup(None) must be called before session.add
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_handler_edit_before_db_write(mock_callback, fsm_context, monkeypatch):
    await fsm_context.update_data(current_task_id=1)
    mock_callback.data = "answer:1:0"

    call_order: list[str] = []

    async def track_edit(**kwargs):
        call_order.append("edit_reply_markup")

    def track_add(obj):
        call_order.append("session.add")

    session, _ = _make_mock_session()
    mock_callback.message.edit_reply_markup = AsyncMock(side_effect=track_edit)
    session.add = MagicMock(side_effect=track_add)

    monkeypatch.setattr("app.bot.handlers.check_answer.AsyncSessionLocal", lambda: session)

    await answer_handler(mock_callback, fsm_context)

    assert "edit_reply_markup" in call_order
    assert "session.add" in call_order
    assert call_order.index("edit_reply_markup") < call_order.index("session.add")
