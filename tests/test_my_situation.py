import pytest
from unittest.mock import AsyncMock, MagicMock

from app.bot.handlers.my_situation import process_situation, process_situation_non_text
from app.bot.states import UserState


# ---------------------------------------------------------------------------
# T5 — photo input: fallback fires, state NOT cleared
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_text_photo_gets_fallback(mock_message, fsm_context):
    mock_message.text = None
    mock_message.photo = [MagicMock()]  # non-empty photo list

    await fsm_context.set_state(UserState.waiting_for_situation)
    await process_situation_non_text(mock_message, fsm_context)

    mock_message.answer.assert_awaited_once()
    answer_text = mock_message.answer.call_args[0][0]
    assert "текстовое описание" in answer_text

    # State must not be cleared — user stays in waiting_for_situation
    assert await fsm_context.get_state() == UserState.waiting_for_situation.state


# ---------------------------------------------------------------------------
# T6 — full happy-path: text input processed by Claude, state cleared
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_situation_full_happy_path(mock_message, fsm_context, fake_redis, monkeypatch):
    mock_message.text = "Начальник накричал, наверное я плохой работник"

    # Redirect aioredis.from_url to fake_redis so no real Redis is needed
    monkeypatch.setattr(
        "app.bot.handlers.my_situation.aioredis.from_url",
        lambda url: fake_redis,
    )

    # Mock Anthropic client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="1. 🧐 Когнитивное искажение: Чтение мыслей...")]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 100

    mock_client_create = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(
        "app.bot.handlers.my_situation.client.messages.create",
        mock_client_create,
    )

    # Mock DB session for TokenUsage logging (handler has except Exception so it won't fail)
    mock_token_session = AsyncMock()
    mock_token_session.__aenter__ = AsyncMock(return_value=mock_token_session)
    mock_token_session.__aexit__ = AsyncMock(return_value=False)
    mock_token_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=1)))
    mock_token_session.add = MagicMock()
    mock_token_session.commit = AsyncMock()
    monkeypatch.setattr(
        "app.bot.handlers.my_situation.AsyncSessionLocal",
        lambda: mock_token_session,
    )

    await fsm_context.set_state(UserState.waiting_for_situation)
    await process_situation(mock_message, fsm_context)

    mock_client_create.assert_awaited_once()
    mock_message.answer.assert_awaited()
    answer_text = mock_message.answer.call_args[0][0]
    assert "Когнитивное искажение" in answer_text or "🧐" in answer_text

    # State must be cleared after successful processing
    assert await fsm_context.get_state() is None


# ---------------------------------------------------------------------------
# T7 — voice / sticker / document: same fallback, no AttributeError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("msg_type,value", [
    ("voice", MagicMock()),
    ("sticker", MagicMock()),
    ("document", MagicMock()),
])
async def test_non_text_various_types_get_fallback(msg_type, value, mock_message, fsm_context):
    mock_message.text = None
    setattr(mock_message, msg_type, value)

    await fsm_context.set_state(UserState.waiting_for_situation)
    await process_situation_non_text(mock_message, fsm_context)

    mock_message.answer.assert_awaited_once()
    answer_text = mock_message.answer.call_args[0][0]
    assert "текстовое описание" in answer_text

    assert await fsm_context.get_state() == UserState.waiting_for_situation.state
