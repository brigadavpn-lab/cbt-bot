import logging
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.prompts import CBT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic | None:
    global _client
    if _client is None and settings.ANTHROPIC_API_KEY:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def analyze_situation(user_text: str) -> str:
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

    parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip()
