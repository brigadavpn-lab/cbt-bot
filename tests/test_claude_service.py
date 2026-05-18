from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import claude as claude_module
from app.services.prompts import DISTORTIONS


@pytest.fixture(autouse=True)
def reset_client():
    claude_module._client = None
    yield
    claude_module._client = None


async def test_analyze_situation_calls_claude_with_system_prompt(monkeypatch):
    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="разбор ситуации")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )
    create = AsyncMock(return_value=fake_message)
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(claude_module, "get_client", lambda: fake_client)

    result = await claude_module.analyze_situation("Начальник косо посмотрел")

    assert result == "разбор ситуации"
    create.assert_awaited_once()
    kwargs = create.await_args.kwargs
    assert kwargs["model"]
    assert kwargs["messages"] == [{"role": "user", "content": "Начальник косо посмотрел"}]
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


async def test_generate_task_returns_tool_input(monkeypatch):
    valid_payload = {
        "situation": "Анна опоздала на встречу.",
        "thought": "Все думают, что я безответственная!",
        "correct_cognitive_distortion": DISTORTIONS[1],
        "options": [DISTORTIONS[1], DISTORTIONS[3], DISTORTIONS[5]],
        "explanation": "Это чтение мыслей.",
    }
    fake_message = SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", name="return_cbt_task", input=valid_payload),
        ],
        usage=SimpleNamespace(input_tokens=5, output_tokens=10),
    )
    create = AsyncMock(return_value=fake_message)
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(claude_module, "get_client", lambda: fake_client)

    result = await claude_module.generate_task()
    assert result == valid_payload


async def test_generate_task_rejects_correct_not_in_options(monkeypatch):
    bad_payload = {
        "situation": "S",
        "thought": "T",
        "correct_cognitive_distortion": DISTORTIONS[0],
        "options": [DISTORTIONS[1], DISTORTIONS[2], DISTORTIONS[3]],
        "explanation": "E",
    }
    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="return_cbt_task", input=bad_payload)],
        usage=None,
    )
    create = AsyncMock(return_value=fake_message)
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(claude_module, "get_client", lambda: fake_client)

    with pytest.raises(ValueError):
        await claude_module.generate_task()


async def test_generate_task_raises_when_no_tool_use(monkeypatch):
    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="oops")],
        usage=None,
    )
    create = AsyncMock(return_value=fake_message)
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(claude_module, "get_client", lambda: fake_client)

    with pytest.raises(ValueError):
        await claude_module.generate_task()
