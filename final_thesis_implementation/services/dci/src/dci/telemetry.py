from __future__ import annotations

import os
import sys
from typing import Optional


DEFAULT_LANGTRACE_API_HOST = "https://omen-server.tail5e5a2f.ts.net/api/trace"

_initialized = False
_enabled = False


def env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def langtrace_capture_content() -> bool:
    """Whether prompts, answers, tool arguments, and tool results may be exported."""
    return env_flag("LANGTRACE_CAPTURE_CONTENT", default=False)


def initialize_langtrace(*, service_name: str) -> bool:
    """Initialize Langtrace once, returning whether trace export is enabled.

    Missing or invalid telemetry configuration never prevents a DCI run. The
    legacy LANGTRACE key is accepted so existing Slurm environments continue to
    work while callers migrate to LANGTRACE_API_KEY.
    """
    global _enabled, _initialized

    if _initialized:
        return _enabled
    _initialized = True

    api_key = (
        os.environ.get("LANGTRACE_API_KEY")
        or os.environ.get("LANGTRACE")
        or ""
    ).strip()
    if not api_key:
        return False

    api_host = (
        os.environ.get("LANGTRACE_API_HOST")
        or DEFAULT_LANGTRACE_API_HOST
    ).strip()
    batch = env_flag("LANGTRACE_BATCH", default=False)
    session_id: Optional[str] = (
        os.environ.get("LANGTRACE_SESSION_ID")
        or os.environ.get("SLURM_JOB_ID")
        or None
    )

    try:
        from langtrace_python_sdk import langtrace

        langtrace.init(
            api_key=api_key,
            api_host=api_host,
            batch=batch,
            service_name=service_name,
            session_id=session_id,
            disable_instrumentations={"all_except": ["openai"]},
        )
    except Exception as exc:
        print(f"[langtrace] initialization failed: {exc}", file=sys.stderr)
        return False

    _enabled = True
    print(
        f"[langtrace] enabled service={service_name} host={api_host}",
        file=sys.stderr,
    )
    return True
