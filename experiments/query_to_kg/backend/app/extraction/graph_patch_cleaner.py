import re
from typing import Any, Mapping

from backend.app.extraction.schemas import EdgeType, GraphPatch, KGEdge, KGNode, NodeType
from backend.app.graph.entity_resolution import canonical_entity_lookup, normalize_entity_text
from backend.app.graph.graph_patch import GraphPatchCleanupResult
from backend.app.graph.validator import validate_graph_patch

_WORD_LIKE_PATTERN = re.compile(r"^[A-Za-z]+$")
_EVIDENCE_PARENT_TYPES = {NodeType.CLAIM, NodeType.METHOD, NodeType.PAPER}


def _slugify_label(label: str) -> str:
    slug = normalize_entity_text(label).replace(" ", "_")
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def _canonicalize_node(node: KGNode) -> tuple[KGNode, str | None]:
    canonical = canonical_entity_lookup(node.type, node.label)
    if canonical is None:
        canonical_id = f"{node.type.value.lower()}:{_slugify_label(node.label)}"
        canonical_label = node.label.strip()
        rewritten = canonical_id != node.id or canonical_label != node.label
        return (
            node.model_copy(
                update={
                    "id": canonical_id,
                    "label": canonical_label,
                }
            ),
            (
                f"Rewrote node '{node.id}' to canonical id '{canonical_id}'."
                if rewritten
                else None
            ),
        )

    rewritten = canonical.canonical_id != node.id or canonical.canonical_label != node.label
    return (
        node.model_copy(
            update={
                "id": canonical.canonical_id,
                "label": canonical.canonical_label,
            }
        ),
        (
            f"Rewrote alias '{node.label}' ({node.id}) to canonical id '{canonical.canonical_id}'."
            if rewritten
            else None
        ),
    )


def _is_word_level_junk(node_type: NodeType, label: str) -> bool:
    cleaned = label.strip()
    if not cleaned:
        return True
    if node_type in {NodeType.PAPER, NodeType.METHOD, NodeType.DATASET, NodeType.BENCHMARK, NodeType.METRIC}:
        return False
    if len(cleaned) <= 2:
        return True
    return bool(_WORD_LIKE_PATTERN.fullmatch(cleaned))


def _dedupe_list(values: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _merge_properties(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    owner: str,
    warnings: list[str],
) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged:
            merged[key] = value
            continue
        if merged[key] != value:
            warnings.append(
                f"Kept existing property '{key}' on {owner} and dropped a conflicting duplicate value."
            )
    return merged


def _merge_node(existing: KGNode, incoming: KGNode, original_id: str, warnings: list[str]) -> KGNode:
    merged_properties = _merge_properties(
        existing.properties,
        incoming.properties,
        owner=f"node '{existing.id}'",
        warnings=warnings,
    )

    aliases = _dedupe_list(
        [
            *existing.properties.get("aliases", []),
            *( [existing.label] if existing.label != existing.id else [] ),
            *( [incoming.label] if incoming.label != existing.label else [] ),
        ]
    )
    merged_from_ids = _dedupe_list(
        [
            *existing.properties.get("merged_from_ids", []),
            original_id,
        ]
    )
    merged_provenance = _dedupe_list(
        [
            *existing.properties.get("merged_provenance", []),
            incoming.provenance.model_dump(),
        ]
    )

    if aliases:
        merged_properties["aliases"] = aliases
    if merged_from_ids:
        merged_properties["merged_from_ids"] = merged_from_ids
    if merged_provenance:
        merged_properties["merged_provenance"] = merged_provenance

    return existing.model_copy(update={"properties": merged_properties})


def _merge_edge(existing: KGEdge, incoming: KGEdge, warnings: list[str]) -> KGEdge:
    merged_properties = _merge_properties(
        existing.properties,
        incoming.properties,
        owner=(
            f"edge '{existing.source}' -[{existing.type.value}]-> '{existing.target}'"
        ),
        warnings=warnings,
    )
    merged_provenance = _dedupe_list(
        [
            *existing.properties.get("merged_provenance", []),
            incoming.provenance.model_dump(),
        ]
    )
    if merged_provenance:
        merged_properties["merged_provenance"] = merged_provenance
    return existing.model_copy(update={"properties": merged_properties})


class GraphPatchCleaner:
    """Clean extracted graph patches without introducing unsupported graph content."""

    def clean(
        self,
        patch: GraphPatch | dict[str, Any],
        chunk_text_by_id: Mapping[str, str] | None = None,
    ) -> GraphPatchCleanupResult:
        graph_patch = patch if isinstance(patch, GraphPatch) else GraphPatch(**patch)
        warnings: list[str] = []

        original_to_canonical: dict[str, str] = {}
        nodes_by_id: dict[str, KGNode] = {}

        for node in graph_patch.nodes:
            canonical_node, rewrite_warning = _canonicalize_node(node)
            original_to_canonical[node.id] = canonical_node.id
            if rewrite_warning:
                warnings.append(rewrite_warning)

            if canonical_node.id in nodes_by_id:
                warnings.append(
                    f"Merged duplicate node '{node.id}' into canonical node '{canonical_node.id}'."
                )
                nodes_by_id[canonical_node.id] = _merge_node(
                    nodes_by_id[canonical_node.id],
                    canonical_node,
                    original_id=node.id,
                    warnings=warnings,
                )
                continue

            initial_properties = dict(canonical_node.properties)
            if canonical_node.id != node.id:
                initial_properties["merged_from_ids"] = [node.id]
                initial_properties["merged_provenance"] = [node.provenance.model_dump()]
            nodes_by_id[canonical_node.id] = canonical_node.model_copy(
                update={"properties": initial_properties}
            )

        edges_by_key: dict[tuple[str, str, EdgeType], KGEdge] = {}
        for edge in graph_patch.edges:
            source = original_to_canonical.get(edge.source, edge.source)
            target = original_to_canonical.get(edge.target, edge.target)
            if source != edge.source or target != edge.target:
                warnings.append(
                    "Rewrote edge endpoints "
                    f"'{edge.source}' -> '{source}' and '{edge.target}' -> '{target}'."
                )
            rewritten_edge = edge.model_copy(update={"source": source, "target": target})
            edge_key = (rewritten_edge.source, rewritten_edge.target, rewritten_edge.type)
            if edge_key in edges_by_key:
                warnings.append(
                    "Merged duplicate edge "
                    f"'{rewritten_edge.source}' -[{rewritten_edge.type.value}]-> '{rewritten_edge.target}'."
                )
                edges_by_key[edge_key] = _merge_edge(edges_by_key[edge_key], rewritten_edge, warnings)
                continue
            edges_by_key[edge_key] = rewritten_edge

        removable_node_ids = {
            node_id
            for node_id, node in nodes_by_id.items()
            if _is_word_level_junk(node.type, node.label)
        }
        for node_id in sorted(removable_node_ids):
            warnings.append(
                f"Removed low-quality node '{node_id}' with label '{nodes_by_id[node_id].label}'."
            )
            nodes_by_id.pop(node_id, None)

        filtered_edges: list[KGEdge] = []
        for edge in edges_by_key.values():
            if edge.source not in nodes_by_id or edge.target not in nodes_by_id:
                warnings.append(
                    "Dropped edge "
                    f"'{edge.source}' -[{edge.type.value}]-> '{edge.target}' because one endpoint was removed."
                )
                continue
            filtered_edges.append(edge)

        filtered_edges = self._prune_disconnected_evidence(nodes_by_id, filtered_edges, warnings)
        cleaned_patch = GraphPatch(nodes=list(nodes_by_id.values()), edges=filtered_edges)
        validation_report = validate_graph_patch(cleaned_patch, chunk_text_by_id=chunk_text_by_id)
        if validation_report.warnings:
            warnings.extend(validation_report.warnings)

        return GraphPatchCleanupResult(
            patch=cleaned_patch,
            warnings=warnings,
            validation_report=validation_report,
        )

    @staticmethod
    def _prune_disconnected_evidence(
        nodes_by_id: dict[str, KGNode],
        edges: list[KGEdge],
        warnings: list[str],
    ) -> list[KGEdge]:
        while True:
            connected_evidence_ids = {
                edge.source
                for edge in edges
                if edge.type == EdgeType.SUPPORTED_BY
                and nodes_by_id.get(edge.source) is not None
                and nodes_by_id[edge.source].type == NodeType.EVIDENCE
                and nodes_by_id.get(edge.target) is not None
                and nodes_by_id[edge.target].type in _EVIDENCE_PARENT_TYPES
            }
            disconnected = [
                node_id
                for node_id, node in nodes_by_id.items()
                if node.type == NodeType.EVIDENCE and node_id not in connected_evidence_ids
            ]
            if not disconnected:
                return edges

            removed = set(disconnected)
            for node_id in disconnected:
                warnings.append(
                    f"Removed disconnected evidence node '{node_id}' because it was not linked to a claim, method, or paper."
                )
                nodes_by_id.pop(node_id, None)

            next_edges: list[KGEdge] = []
            for edge in edges:
                if edge.source in removed or edge.target in removed:
                    warnings.append(
                        "Dropped edge "
                        f"'{edge.source}' -[{edge.type.value}]-> '{edge.target}' after removing disconnected evidence."
                    )
                    continue
                next_edges.append(edge)
            edges = next_edges


def clean_graph_patch(
    patch: GraphPatch | dict[str, Any],
    chunk_text_by_id: Mapping[str, str] | None = None,
) -> GraphPatchCleanupResult:
    """Apply post-extraction cleanup and return the cleaned patch plus diagnostics."""
    return GraphPatchCleaner().clean(patch, chunk_text_by_id=chunk_text_by_id)
