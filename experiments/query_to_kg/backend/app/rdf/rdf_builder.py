import re
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal
from rdflib.namespace import RDF

from backend.app.extraction.schemas import EdgeType, GraphPatch, KGEdge, KGNode, NodeType
from backend.app.rdf.namespace import KG, bind_namespaces
from backend.app.rdf.rdf_schema import (
    EDGE_TO_PREDICATE_NAME,
    NODE_PROPERTY_TO_PREDICATE_NAME,
    NODE_TYPE_TO_CLASS_NAME,
    PROVENANCE_TO_PREDICATE_NAME,
)

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9_]+")


def _slugify(value: str) -> str:
    normalized = value.strip().lower().replace(":", "_").replace("-", "_").replace(" ", "_")
    normalized = _NON_ALNUM_PATTERN.sub("_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "resource"


def node_id_to_term(node_id: str):
    return KG[_slugify(node_id)]


def _literalize(value: Any) -> Literal:
    return Literal(value)


class RDFBuilder:
    """Convert a validated graph patch into an RDFLib graph."""

    def build(self, patch: GraphPatch | dict[str, Any]) -> Graph:
        graph_patch = patch if isinstance(patch, GraphPatch) else GraphPatch(**patch)
        graph = bind_namespaces(Graph())

        node_terms = {node.id: node_id_to_term(node.id) for node in graph_patch.nodes}

        for node in graph_patch.nodes:
            node_term = node_terms[node.id]
            graph.add((node_term, RDF.type, KG[NODE_TYPE_TO_CLASS_NAME[node.type]]))
            self._add_label_triples(graph, node_term, node)
            self._add_property_triples(graph, node_term, node)
            self._add_provenance_triples(graph, node_term, node)

        for edge in graph_patch.edges:
            graph.add(
                (
                    node_terms[edge.source],
                    KG[EDGE_TO_PREDICATE_NAME[edge.type]],
                    node_terms[edge.target],
                )
            )
            self._add_edge_evidence_triples(graph, node_terms, graph_patch, edge)

        return graph

    def serialize(self, graph: Graph, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        graph.serialize(destination=destination, format="turtle")
        return destination

    @staticmethod
    def _add_label_triples(graph: Graph, node_term, node: KGNode) -> None:
        label = node.label.strip()
        if not label:
            return

        if node.type == NodeType.PAPER:
            graph.add((node_term, KG.name, _literalize(label)))
            return

        if node.type in {NodeType.CLAIM, NodeType.EVIDENCE, NodeType.LIMITATION} and "text" not in node.properties:
            graph.add((node_term, KG.text, _literalize(label)))
            return

        graph.add((node_term, KG.name, _literalize(label)))

    @staticmethod
    def _add_property_triples(graph: Graph, node_term, node: KGNode) -> None:
        for key, predicate_name in NODE_PROPERTY_TO_PREDICATE_NAME.items():
            value = node.properties.get(key)
            if value in (None, ""):
                continue
            graph.add((node_term, KG[predicate_name], _literalize(value)))

        if node.type == NodeType.PAPER and "title" not in node.properties and node.provenance.paper_title:
            graph.add((node_term, KG.title, _literalize(node.provenance.paper_title)))

        if node.type == NodeType.EVIDENCE and "text" not in node.properties and node.provenance.text_span:
            graph.add((node_term, KG.text, _literalize(node.provenance.text_span)))

    @staticmethod
    def _add_provenance_triples(graph: Graph, node_term, node: KGNode) -> None:
        provenance = node.provenance.model_dump()
        for key, predicate_name in PROVENANCE_TO_PREDICATE_NAME.items():
            value = provenance.get(key)
            if value in (None, ""):
                continue
            graph.add((node_term, KG[predicate_name], _literalize(value)))

    @staticmethod
    def _add_edge_evidence_triples(
        graph: Graph,
        node_terms: dict[str, Any],
        graph_patch: GraphPatch,
        edge: KGEdge,
    ) -> None:
        source_node = next(node for node in graph_patch.nodes if node.id == edge.source)
        target_node = next(node for node in graph_patch.nodes if node.id == edge.target)

        if edge.type == EdgeType.FROM_PAPER and source_node.type == NodeType.METHOD and target_node.type == NodeType.PAPER:
            graph.add((node_terms[target_node.id], KG.proposes, node_terms[source_node.id]))
        else:
            return

        if not edge.provenance.text_span:
            return

        evidence_term = KG[
            _slugify(
                "evidence:"
                f"{edge.provenance.chunk_id}:"
                f"{edge.type.value}:"
                f"{edge.source}:"
                f"{edge.target}"
            )
        ]
        graph.add((evidence_term, RDF.type, KG.Evidence))
        graph.add((evidence_term, KG.text, _literalize(edge.provenance.text_span)))
        graph.add((node_terms[edge.source], KG.supportedBy, evidence_term))

        provenance = edge.provenance.model_dump()
        for key, predicate_name in PROVENANCE_TO_PREDICATE_NAME.items():
            value = provenance.get(key)
            if value in (None, ""):
                continue
            graph.add((evidence_term, KG[predicate_name], _literalize(value)))


def build_rdf_graph(patch: GraphPatch | dict[str, Any]) -> Graph:
    return RDFBuilder().build(patch)
