from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config import LoggingConfig

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover - uv sync installs structlog
    structlog = None  # type: ignore


class _FallbackLogger:
    def __init__(self, logger: logging.Logger, context: dict[str, Any] | None = None) -> None:
        self._logger = logger
        self._context = context or {}

    def bind(self, **context: Any) -> "_FallbackLogger":
        return _FallbackLogger(self._logger, {**self._context, **context})

    def _msg(self, event: str, kwargs: dict[str, Any]) -> str:
        merged = {**self._context, **kwargs}
        tail = " ".join(f"{k}={v!r}" for k, v in sorted(merged.items()))
        return f"{event} {tail}".rstrip()

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info(self._msg(event, kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning(self._msg(event, kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error(self._msg(event, kwargs))

    def exception(self, event: str, **kwargs: Any) -> None:
        self._logger.exception(self._msg(event, kwargs))


def configure_logging(config: LoggingConfig) -> None:
    level = getattr(logging, config.level.upper(), logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if structlog is None:
        handlers: list[logging.Handler] = [logging.StreamHandler()]
        if config.file is not None:
            path = Path(config.file)
            path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(path, encoding="utf-8"))
        logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)
        return

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    renderer = structlog.processors.JSONRenderer() if config.json else structlog.dev.ConsoleRenderer(colors=config.colors)
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    if config.file is not None:
        path = Path(config.file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=shared_processors,
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        root.addHandler(file_handler)
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(**context: Any):
    if structlog is None:
        return _FallbackLogger(logging.getLogger("query_driven"), context)
    return structlog.get_logger().bind(**context)
