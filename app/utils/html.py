from html import escape


def esc(text: str | None) -> str:
    """Экранирует текст для безопасной вставки в HTML-режиме Telegram."""
    if text is None:
        return ''
    return escape(str(text))
