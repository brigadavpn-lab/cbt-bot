import logging

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.prompts import (
    CBT_SYSTEM_PROMPT,
    DISTORTIONS,
    TASK_GENERATOR_SYSTEM_PROMPT,
)
from app.services.usage_logger import Usage

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic | None:
    global _client
    if _client is None and settings.ANTHROPIC_API_KEY:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _extract_usage(message) -> Usage:
    raw = getattr(message, "usage", None)
    if raw is None:
        return Usage()
    return Usage(
        input_tokens=getattr(raw, "input_tokens", 0) or 0,
        output_tokens=getattr(raw, "output_tokens", 0) or 0,
        cache_read_input_tokens=getattr(raw, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(raw, "cache_creation_input_tokens", 0) or 0,
    )


def _log_usage_struct(op: str, usage: Usage) -> None:
    logger.info(
        "claude_usage",
        extra={
            "op": op,
            "model": settings.CLAUDE_MODEL,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        },
    )


async def analyze_situation(user_text: str) -> tuple[str, Usage]:
    client = get_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    message = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": CBT_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    usage = _extract_usage(message)
    _log_usage_struct("analyze_situation", usage)

    parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip(), usage


_TASK_TOOL = {
    "name": "return_cbt_task",
    "description": "Возвращает один учебный кейс по КПТ строго в заданной структуре.",
    "input_schema": {
        "type": "object",
        "properties": {
            "situation": {"type": "string", "description": "Текст ситуации, 2-4 предложения."},
            "thought": {"type": "string", "description": "Автоматическая мысль, эмоциональная."},
            "correct_cognitive_distortion": {
                "type": "string",
                "enum": DISTORTIONS,
            },
            "options": {
                "type": "array",
                "items": {"type": "string", "enum": DISTORTIONS},
                "minItems": 3,
                "maxItems": 3,
            },
            "explanation": {"type": "string"},
        },
        "required": [
            "situation",
            "thought",
            "correct_cognitive_distortion",
            "options",
            "explanation",
        ],
    },
}


async def generate_task() -> tuple[dict, Usage]:
    client = get_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    message = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": TASK_GENERATOR_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_TASK_TOOL],
        tool_choice={"type": "tool", "name": "return_cbt_task"},
        messages=[{"role": "user", "content": "Сгенерируй один кейс."}],
    )
    usage = _extract_usage(message)
    _log_usage_struct("generate_task", usage)

    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "return_cbt_task":
            data = dict(block.input)
            if data["correct_cognitive_distortion"] not in data["options"]:
                raise ValueError("correct answer is not present in options")
            return data, usage

    raise ValueError("Claude did not return a tool_use block")
