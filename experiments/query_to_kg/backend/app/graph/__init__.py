"""Graph utilities for query-to-KG milestone work."""

from .graph_patch import GraphPatchCleanupResult
from .entity_resolution import (
    EntityResolver,
    canonical_entity_lookup,
    normalize_entity_text,
    resolve_graph_patch,
)
from .validator import GraphPatchValidator, validate_graph_patch
from backend.app.extraction.graph_patch_cleaner import GraphPatchCleaner, clean_graph_patch

__all__ = [
    "EntityResolver",
    "GraphPatchCleaner",
    "GraphPatchCleanupResult",
    "GraphPatchValidator",
    "canonical_entity_lookup",
    "clean_graph_patch",
    "normalize_entity_text",
    "resolve_graph_patch",
    "validate_graph_patch",
]
