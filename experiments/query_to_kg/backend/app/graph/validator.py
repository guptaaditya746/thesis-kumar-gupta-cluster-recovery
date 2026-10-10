import re
from collections import Counter
from typing import Any, Mapping

from pydantic import ValidationError

from backend.app.extraction.schemas import EdgeType, GraphPatch, NodeType, ValidationReport

_WORD_LIKE_PATTERN = re.compile(r"^[A-Za-z]+$")


def _is_word_level_junk(node_type: NodeType, label: str) -> bool:
    cleaned = label.strip()
    if not cleaned:
        return True
    if node_type in {NodeType.PAPER, NodeType.METHOD, NodeType.DATASET, NodeType.BENCHMARK, NodeType.METRIC}:
        return False
    if len(cleaned) <= 2:
        return True
    return bool(_WORD_LIKE_PATTERN.fullmatch(cleaned))


class GraphPatchValidator:
    """Validates graph patches after extraction and entity resolution."""

    def validate(
        self,
        patch: GraphPatch | dict[str, Any],
        chunk_text_by_id: Mapping[str, str] | None = None,
    ) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []

        try:
            graph_patch = patch if isinstance(patch, GraphPatch) else GraphPatch(**patch)
        except ValidationError as exc:
            return ValidationReport(
                is_valid=False,
                errors=[self._format_schema_error(err) for err in exc.errors()],
                warnings=[],
                node_count=len(patch.get("nodes", [])) if isinstance(patch, dict) else 0,
                edge_count=len(patch.get("edges", [])) if isinstance(patch, dict) else 0,
            )

        node_ids = [node.id for node in graph_patch.nodes]
        duplicate_ids = [node_id for node_id, count in Counter(node_ids).items() if count > 1]
        for node_id in duplicate_ids:
            errors.append(f"Duplicate node ID detected: '{node_id}'.")

        node_id_set = set(node_ids)
        for edge in graph_patch.edges:
            if edge.source not in node_id_set:
                errors.append(
                    f"Edge '{edge.type.value}' references missing source node '{edge.source}'."
                )
            if edge.target not in node_id_set:
                errors.append(
                    f"Edge '{edge.type.value}' references missing target node '{edge.target}'."
                )

        for node in graph_patch.nodes:
            self._validate_provenance(
                owner=f"Node '{node.id}'",
                provenance=node.provenance,
                errors=errors,
                warnings=warnings,
                chunk_text_by_id=chunk_text_by_id,
            )
            if _is_word_level_junk(node.type, node.label):
                errors.append(
                    f"Node '{node.id}' has a likely word-level junk label '{node.label}'."
                )

        for index, edge in enumerate(graph_patch.edges, start=1):
            self._validate_provenance(
                owner=f"Edge #{index} ({edge.source} -[{edge.type.value}]-> {edge.target})",
                provenance=edge.provenance,
                errors=errors,
                warnings=warnings,
                chunk_text_by_id=chunk_text_by_id,
            )

        supported_evidence_nodes = {
            edge.source
            for edge in graph_patch.edges
            if edge.type == EdgeType.SUPPORTED_BY
        }
        for node in graph_patch.nodes:
            if node.type == NodeType.EVIDENCE and node.id not in supported_evidence_nodes:
                warnings.append(
                    f"Evidence node '{node.id}' is isolated from any SUPPORTED_BY edge."
                )

        return ValidationReport(
            is_valid=not errors,
            errors=errors,
            warnings=warnings,
            node_count=len(graph_patch.nodes),
            edge_count=len(graph_patch.edges),
        )

    @staticmethod
    def _format_schema_error(error: dict[str, Any]) -> str:
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "Schema validation failed.")
        if location:
            return f"Schema validation failed at '{location}': {message}"
        return f"Schema validation failed: {message}"

    @staticmethod
    def _validate_provenance(
        owner: str,
        provenance: Any,
        errors: list[str],
        warnings: list[str],
        chunk_text_by_id: Mapping[str, str] | None,
    ) -> None:
        if not provenance.paper_id.strip():
            errors.append(f"{owner} is missing a non-empty provenance.paper_id.")
        if not provenance.chunk_id.strip():
            errors.append(f"{owner} is missing a non-empty provenance.chunk_id.")
        if not provenance.text_span.strip():
            errors.append(f"{owner} is missing a non-empty provenance.text_span.")
            return

        if chunk_text_by_id is None:
            return

        raw_text = chunk_text_by_id.get(provenance.chunk_id)
        if raw_text is None:
            warnings.append(
                f"{owner} provenance.chunk_id '{provenance.chunk_id}' was not found in provided chunk text."
            )
            return
        if provenance.text_span not in raw_text:
            errors.append(
                f"{owner} provenance.text_span is not a direct substring of chunk '{provenance.chunk_id}'."
            )


def validate_graph_patch(
    patch: GraphPatch | dict[str, Any],
    chunk_text_by_id: Mapping[str, str] | None = None,
) -> ValidationReport:
    """Validate a graph patch and return a structured report."""
    return GraphPatchValidator().validate(patch, chunk_text_by_id=chunk_text_by_id)
