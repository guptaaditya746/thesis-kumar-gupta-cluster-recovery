import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from backend.app.extraction.schemas import GraphPatch, KGEdge, KGNode, NodeType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalEntity:
    canonical_id: str
    canonical_label: str


def normalize_entity_text(text: str) -> str:
    """Normalize an entity string for dictionary lookup."""
    cleaned = text.lower().replace("-", " ").replace("_", " ")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


_CANONICAL_ALIASES: dict[NodeType, dict[str, CanonicalEntity]] = {
    NodeType.PAPER: {
        "lightrag": CanonicalEntity("paper:lightrag", "LightRAG"),
        "light rag": CanonicalEntity("paper:lightrag", "LightRAG"),
    },
    NodeType.METHOD: {
        "autograph r1": CanonicalEntity("method:autograph_r1", "AutoGraph-R1"),
        "autograph r1 framework": CanonicalEntity("method:autograph_r1", "AutoGraph-R1"),
    },
    NodeType.BENCHMARK: {
        "mind the query": CanonicalEntity("benchmark:mind_the_query", "Mind the Query"),
        "text2cypher benchmark": CanonicalEntity("benchmark:mind_the_query", "Mind the Query"),
    },
    NodeType.TASK: {
        "knowledge graph construction": CanonicalEntity(
            "task:knowledge_graph_construction",
            "Knowledge Graph Construction",
        ),
        "kg construction": CanonicalEntity(
            "task:knowledge_graph_construction",
            "Knowledge Graph Construction",
        ),
    },
}


def canonical_entity_lookup(node_type: NodeType, label: str) -> Optional[CanonicalEntity]:
    """Return a canonical entity mapping for a node label if it is an obvious alias."""
    normalized = normalize_entity_text(label)
    return _CANONICAL_ALIASES.get(node_type, {}).get(normalized)


def _slugify_label(label: str) -> str:
    slug = normalize_entity_text(label).replace(" ", "_")
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def _canonicalize_node(node: KGNode) -> tuple[KGNode, bool]:
    canonical = canonical_entity_lookup(node.type, node.label)
    if canonical is None:
        canonical_id = f"{node.type.value.lower()}:{_slugify_label(node.label)}"
        canonical_label = node.label.strip()
        return (
            node.model_copy(
                update={
                    "id": canonical_id,
                    "label": canonical_label,
                }
            ),
            False,
        )

    rewritten = canonical.canonical_id != node.id or canonical.canonical_label != node.label
    if rewritten:
        logger.warning(
            "Rewriting alias '%s' to canonical id '%s' for type '%s'.",
            node.label,
            canonical.canonical_id,
            node.type.value,
        )
    return (
        node.model_copy(
            update={
                "id": canonical.canonical_id,
                "label": canonical.canonical_label,
            }
        ),
        rewritten,
    )


def _merge_properties(existing: dict[str, Any], incoming: dict[str, Any], node_id: str) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged:
            merged[key] = value
            continue
        if merged[key] != value:
            logger.warning(
                "Preserving existing property '%s' on canonical node '%s' while dropping conflicting value.",
                key,
                node_id,
            )
    return merged


class EntityResolver:
    """Dictionary-based entity resolution for the M3 graph patch MVP."""

    def resolve(self, patch: GraphPatch | dict[str, Any]) -> GraphPatch:
        graph_patch = patch if isinstance(patch, GraphPatch) else GraphPatch(**patch)

        original_to_canonical: dict[str, str] = {}
        nodes_by_id: dict[str, KGNode] = {}

        for node in graph_patch.nodes:
            resolved_node, rewritten = _canonicalize_node(node)
            original_to_canonical[node.id] = resolved_node.id

            if resolved_node.id in nodes_by_id:
                logger.warning(
                    "Merging node '%s' into canonical node '%s'.",
                    node.id,
                    resolved_node.id,
                )
                existing = nodes_by_id[resolved_node.id]
                merged_properties = _merge_properties(existing.properties, resolved_node.properties, resolved_node.id)
                nodes_by_id[resolved_node.id] = existing.model_copy(
                    update={
                        "properties": merged_properties,
                    }
                )
                continue

            if rewritten and node.id != resolved_node.id:
                logger.warning(
                    "Rewrote node id '%s' to '%s'.",
                    node.id,
                    resolved_node.id,
                )
            nodes_by_id[resolved_node.id] = resolved_node

        resolved_edges: list[KGEdge] = []
        for edge in graph_patch.edges:
            source = original_to_canonical.get(edge.source, edge.source)
            target = original_to_canonical.get(edge.target, edge.target)
            if source != edge.source or target != edge.target:
                logger.warning(
                    "Rewrote edge endpoints '%s' -> '%s' and '%s' -> '%s'.",
                    edge.source,
                    source,
                    edge.target,
                    target,
                )
            resolved_edges.append(
                edge.model_copy(
                    update={
                        "source": source,
                        "target": target,
                    }
                )
            )

        return GraphPatch(nodes=list(nodes_by_id.values()), edges=resolved_edges)


def resolve_graph_patch(patch: GraphPatch | dict[str, Any]) -> GraphPatch:
    """Resolve aliases and deduplicate obvious duplicate entities in a graph patch."""
    return EntityResolver().resolve(patch)
