from backend.app.extraction.graph_patch_cleaner import clean_graph_patch
from backend.app.extraction.schemas import GraphPatch, KGEdge, KGNode, NodeType, EdgeType, Provenance


def _provenance(
    paper_id: str = "test_paper",
    chunk_id: str = "chunk_001",
    text_span: str = "evidence span",
) -> Provenance:
    return Provenance(
        paper_id=paper_id,
        chunk_id=chunk_id,
        text_span=text_span,
    )


def test_cleaner_rewrites_ids_merges_duplicates_and_preserves_edge_references():
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="paper_a",
                type=NodeType.PAPER,
                label="LightRAG",
                properties={"year": 2024},
                provenance=_provenance(text_span="LightRAG"),
            ),
            KGNode(
                id="paper_b",
                type=NodeType.PAPER,
                label="light rag",
                properties={"venue": "arXiv"},
                provenance=_provenance(text_span="light rag"),
            ),
            KGNode(
                id="claim_1",
                type=NodeType.CLAIM,
                label="Improves retrieval quality",
                provenance=_provenance(text_span="improves retrieval quality"),
            ),
        ],
        edges=[
            KGEdge(
                source="paper_a",
                target="claim_1",
                type=EdgeType.MAKES_CLAIM,
                provenance=_provenance(text_span="LightRAG improves retrieval quality"),
            ),
            KGEdge(
                source="paper_b",
                target="claim_1",
                type=EdgeType.MAKES_CLAIM,
                provenance=_provenance(text_span="light rag improves retrieval quality"),
            ),
        ],
    )

    result = clean_graph_patch(patch)

    assert result.validation_report.is_valid is True
    assert len(result.patch.nodes) == 2
    canonical_paper = next(node for node in result.patch.nodes if node.type == NodeType.PAPER)
    assert canonical_paper.id == "paper:lightrag"
    assert canonical_paper.properties["year"] == 2024
    assert canonical_paper.properties["venue"] == "arXiv"
    assert canonical_paper.properties["merged_from_ids"] == ["paper_a", "paper_b"]
    assert len(result.patch.edges) == 1
    assert result.patch.edges[0].source == "paper:lightrag"
    assert any("Merged duplicate node" in warning for warning in result.warnings)
    assert any("Merged duplicate edge" in warning for warning in result.warnings)


def test_cleaner_removes_word_level_junk_nodes_and_incident_edges():
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="paper_1",
                type=NodeType.PAPER,
                label="AutoGraph-R1",
                provenance=_provenance(text_span="AutoGraph-R1"),
            ),
            KGNode(
                id="claim_1",
                type=NodeType.CLAIM,
                label="Graph",
                provenance=_provenance(text_span="Graph"),
            ),
        ],
        edges=[
            KGEdge(
                source="paper_1",
                target="claim_1",
                type=EdgeType.MAKES_CLAIM,
                provenance=_provenance(text_span="Graph"),
            )
        ],
    )

    result = clean_graph_patch(patch)

    assert result.validation_report.is_valid is True
    assert [node.id for node in result.patch.nodes] == ["paper:autograph_r1"]
    assert result.patch.edges == []
    assert any("Removed low-quality node" in warning for warning in result.warnings)
    assert any("Dropped edge" in warning for warning in result.warnings)


def test_cleaner_prunes_disconnected_evidence_nodes():
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="paper_1",
                type=NodeType.PAPER,
                label="Mind the Query",
                provenance=_provenance(text_span="Mind the Query"),
            ),
            KGNode(
                id="evidence_1",
                type=NodeType.EVIDENCE,
                label="retrieval evidence",
                provenance=_provenance(text_span="retrieval evidence"),
            ),
        ],
        edges=[],
    )

    result = clean_graph_patch(patch)

    assert result.validation_report.is_valid is True
    assert [node.type for node in result.patch.nodes] == [NodeType.PAPER]
    assert result.validation_report.warnings == []
    assert any("Removed disconnected evidence node" in warning for warning in result.warnings)


def test_cleaner_keeps_supported_evidence_connected_to_claim():
    patch = GraphPatch(
        nodes=[
            KGNode(
                id="claim_1",
                type=NodeType.CLAIM,
                label="Improves retrieval quality",
                provenance=_provenance(text_span="improves retrieval quality"),
            ),
            KGNode(
                id="evidence_1",
                type=NodeType.EVIDENCE,
                label="retrieval evidence",
                provenance=_provenance(text_span="retrieval evidence"),
            ),
        ],
        edges=[
            KGEdge(
                source="evidence_1",
                target="claim_1",
                type=EdgeType.SUPPORTED_BY,
                provenance=_provenance(text_span="retrieval evidence"),
            )
        ],
    )

    result = clean_graph_patch(
        patch,
        chunk_text_by_id={
            "chunk_001": "improves retrieval quality with retrieval evidence."
        },
    )

    assert result.validation_report.is_valid is True
    assert len(result.patch.nodes) == 2
    assert len(result.patch.edges) == 1
    assert result.validation_report.warnings == []
