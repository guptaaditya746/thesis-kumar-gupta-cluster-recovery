import logging

from backend.app.extraction.schemas import GraphPatch, KGNode, NodeType, Provenance
from backend.app.graph.entity_resolution import normalize_entity_text, resolve_graph_patch


def _provenance() -> dict[str, str]:
    return {
        "paper_id": "test_paper",
        "chunk_id": "test_chunk",
        "text_span": "evidence span",
    }


def test_normalize_entity_text_handles_punctuation_and_spacing():
    assert normalize_entity_text("  AutoGraph-R1 framework  ") == "autograph r1 framework"
    assert normalize_entity_text("LightRAG!") == "lightrag"
    assert normalize_entity_text("Mind   the   Query") == "mind the query"


def test_resolve_autograph_r1_aliases_to_canonical_id(caplog):
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="node_1",
                type=NodeType.METHOD,
                label="AutoGraph-R1",
                provenance=Provenance(**_provenance()),
            ),
            KGNode(
                id="node_2",
                type=NodeType.METHOD,
                label="autograph r1 framework",
                provenance=Provenance(**_provenance()),
            ),
        ],
        edges=[],
    )

    with caplog.at_level(logging.WARNING):
        resolved = resolve_graph_patch(patch)

    assert len(resolved.nodes) == 1
    assert resolved.nodes[0].id == "method:autograph_r1"
    assert resolved.nodes[0].label == "AutoGraph-R1"
    assert any("Rewriting alias" in record.message for record in caplog.records)
    assert any("Merging node" in record.message for record in caplog.records)


def test_resolve_lightrag_aliases_to_canonical_id(caplog):
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="paper_a",
                type=NodeType.PAPER,
                label="LightRAG",
                provenance=Provenance(**_provenance()),
            ),
            KGNode(
                id="paper_b",
                type=NodeType.PAPER,
                label="light rag",
                provenance=Provenance(**_provenance()),
            ),
        ],
        edges=[],
    )

    with caplog.at_level(logging.WARNING):
        resolved = resolve_graph_patch(patch)

    assert len(resolved.nodes) == 1
    assert resolved.nodes[0].id == "paper:lightrag"
    assert resolved.nodes[0].label == "LightRAG"
    assert any("Merging node" in record.message for record in caplog.records)


def test_resolve_mind_the_query_and_text2cypher_aliases(caplog):
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="bench_1",
                type=NodeType.BENCHMARK,
                label="Mind the Query",
                provenance=Provenance(**_provenance()),
            ),
            KGNode(
                id="bench_2",
                type=NodeType.BENCHMARK,
                label="Text2Cypher benchmark",
                provenance=Provenance(**_provenance()),
            ),
        ],
        edges=[],
    )

    with caplog.at_level(logging.WARNING):
        resolved = resolve_graph_patch(patch)

    assert len(resolved.nodes) == 1
    assert resolved.nodes[0].id == "benchmark:mind_the_query"
    assert resolved.nodes[0].label == "Mind the Query"
    assert any("Rewriting alias" in record.message for record in caplog.records)
    assert any("Merging node" in record.message for record in caplog.records)


def test_non_alias_terms_are_only_normalized_for_ids(caplog):
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="node_1",
                type=NodeType.TASK,
                label="Graph retrieval pipeline",
                provenance=Provenance(**_provenance()),
            )
        ],
        edges=[],
    )

    with caplog.at_level(logging.WARNING):
        resolved = resolve_graph_patch(patch)

    assert len(resolved.nodes) == 1
    assert resolved.nodes[0].id == "task:graph_retrieval_pipeline"
    assert resolved.nodes[0].label == "Graph retrieval pipeline"
    assert not any("Merging node" in record.message for record in caplog.records)
