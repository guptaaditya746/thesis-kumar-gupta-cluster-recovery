"""Compatibility wrapper for local vLLM/LiteLLM settings."""

from backend.app.llm_config import (
    API_KEY,
    CHAT_API_BASE,
    CHAT_MODEL,
    EMBED_API_BASE,
    EMBED_MODEL,
    build_embedding_model,
)

__all__ = [
    "API_KEY",
    "CHAT_API_BASE",
    "CHAT_MODEL",
    "EMBED_API_BASE",
    "EMBED_MODEL",
    "build_embedding_model",
]
