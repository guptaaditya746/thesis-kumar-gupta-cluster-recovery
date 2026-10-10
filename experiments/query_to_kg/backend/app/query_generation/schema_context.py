from typing import Any

from pydantic import BaseModel, Field

from backend.app.extraction.schemas import GraphPatch
from backend.app.rdf.rdf_schema import (
    CLASS_NAMES,
    PREDICATE_NAMES,
    SCHEMA_PREFIXES,
    observed_classes,
    observed_predicates,
)


class SchemaContext(BaseModel):
    prefixes: dict[str, str] = Field(default_factory=dict)
    classes: list[str] = Field(default_factory=list)
    predicates: list[str] = Field(default_factory=list)
    observed_classes: list[str] = Field(default_factory=list)
    observed_predicates: list[str] = Field(default_factory=list)

    def render(self) -> str:
        prefix_lines = [
            f"PREFIX {alias}: <{namespace}>"
            for alias, namespace in self.prefixes.items()
        ]
        classes = ", ".join(self.classes)
        predicates = ", ".join(self.predicates)
        return (
            "Prefixes:\n"
            f"{chr(10).join(prefix_lines)}\n\n"
            f"Classes:\n{classes}\n\n"
            f"Predicates:\n{predicates}"
        )


class SchemaContextBuilder:
    """Build the compact schema context passed to SPARQL generation."""

    def build(self, patch: GraphPatch | dict[str, Any]) -> SchemaContext:
        graph_patch = patch if isinstance(patch, GraphPatch) else GraphPatch(**patch)
        return SchemaContext(
            prefixes=dict(SCHEMA_PREFIXES),
            classes=[f"kg:{name}" for name in CLASS_NAMES],
            predicates=[f"kg:{name}" for name in PREDICATE_NAMES],
            observed_classes=observed_classes(graph_patch),
            observed_predicates=observed_predicates(graph_patch),
        )


def build_graph_summary(patch: GraphPatch | dict[str, Any]) -> str:
    graph_patch = patch if isinstance(patch, GraphPatch) else GraphPatch(**patch)

    node_lines = [
        f"- {node.id} ({node.type.value}): {node.label}"
        for node in graph_patch.nodes
    ]
    edge_lines = [
        f"- {edge.source} -[{edge.type.value}]-> {edge.target}"
        for edge in graph_patch.edges
    ]
    return (
        f"Nodes ({len(graph_patch.nodes)}):\n"
        f"{chr(10).join(node_lines) if node_lines else '- none'}\n\n"
        f"Edges ({len(graph_patch.edges)}):\n"
        f"{chr(10).join(edge_lines) if edge_lines else '- none'}"
    )


def build_schema_context(patch: GraphPatch | dict[str, Any]) -> SchemaContext:
    return SchemaContextBuilder().build(patch)
