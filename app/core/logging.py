import json
import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k in (
                "args",
                "msg",
                "levelname",
                "name",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "levelno",
                "asctime",
            ):
                continue
            try:
                json.dumps(v)
            except (TypeError, ValueError):
                v = repr(v)
            payload[k] = v
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # Отдельный файловый канал для биллинг-учёта токенов.
    # Читается через `tail -f usage.log` на VPS — не зависит от формата root.
    usage = logging.getLogger("usage_stats")
    usage.setLevel(logging.INFO)
    usage.propagate = False
    usage.handlers.clear()
    try:
        usage_handler = RotatingFileHandler(
            settings.USAGE_LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        usage_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        usage.addHandler(usage_handler)
    except OSError:
        # Файловая система может быть недоступна (например, в тестах) — пропускаем.
        pass
