from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

try:
    import structlog  # type: ignore
except ImportError:  # pragma: no cover - fallback only for constrained/offline environments
    structlog = None

_CONFIGURED = False
_FALLBACK_LEVEL = logging.INFO
_FALLBACK_JSON = False


class _FallbackLogger:
    def __init__(self, name: str) -> None:
        self.name = name

    def _emit(self, level: str, event: str, **kwargs: Any) -> None:
        numeric = getattr(logging, level.upper(), logging.INFO)
        if numeric < _FALLBACK_LEVEL:
            return
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.lower(),
            "logger": self.name,
            "event": event,
            **{k: v for k, v in kwargs.items() if k != "exc_info"},
        }
        if _FALLBACK_JSON:
            print(json.dumps(payload, ensure_ascii=False, default=str), file=sys.stderr)
        else:
            details = " ".join(f"{k}={v!r}" for k, v in payload.items() if k not in {"timestamp", "level", "logger", "event"})
            suffix = f" {details}" if details else ""
            print(f"{payload['timestamp']} [{level.upper():7}] {event}{suffix}", file=sys.stderr)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit("debug", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit("info", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit("warning", event, **kwargs)

    warn = warning

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit("error", event, **kwargs)


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structlog once; fall back to a small stderr logger if unavailable."""
    global _CONFIGURED, _FALLBACK_LEVEL, _FALLBACK_JSON
    if _CONFIGURED:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    _FALLBACK_LEVEL = numeric_level
    _FALLBACK_JSON = json_logs

    if structlog is None:
        _CONFIGURED = True
        return

    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=numeric_level)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str = "dci") -> Any:
    if structlog is None:
        return _FallbackLogger(name)
    return structlog.get_logger(name)
