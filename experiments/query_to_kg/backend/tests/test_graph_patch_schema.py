import pytest
from pydantic import ValidationError
from backend.app.extraction.schemas import (
    NodeType,
    EdgeType,
    Provenance,
    KGNode,
    KGEdge,
    GraphPatch,
    ValidationReport,
)
from backend.app.graph.validator import validate_graph_patch

def test_valid_graph_patch_autograph_r1():
    """Test schema with a valid graph patch similar to AutoGraph-R1 demo."""
    provenance = {
        "paper_id": "autograph_r1",
        "chunk_id": "chunk_001",
        "text_span": "we propose AutoGraph-R1, a reinforcement-learning approach for knowledge graph construction",
        "paper_title": "AutoGraph-R1",
        "section_title": "Introduction"
    }
    
    node1 = {
        "id": "node_1",
        "type": "Paper",
        "label": "AutoGraph-R1",
        "properties": {"year": 2024},
        "provenance": provenance
    }
    
    node2 = {
        "id": "node_2",
        "type": "Method",
        "label": "Reinforcement Learning for KG Construction",
        "provenance": provenance
    }
    
    edge = {
        "source": "node_1",
        "target": "node_2",
        "type": "PROPOSES",
        "provenance": provenance
    }
    
    patch_data = {
        "nodes": [node1, node2],
        "edges": [edge]
    }
    
    patch = GraphPatch(**patch_data)
    assert len(patch.nodes) == 2
    assert len(patch.edges) == 1
    assert patch.nodes[0].type == NodeType.PAPER
    assert patch.edges[0].type == EdgeType.PROPOSES
    assert patch.nodes[0].properties == {"year": 2024}

def test_valid_graph_patch_lightrag():
    """Test schema with a valid graph patch similar to LightRAG demo."""
    provenance = {
        "paper_id": "lightrag",
        "chunk_id": "chunk_042",
        "text_span": "graph structures improve retrieval by capturing relationships between entities",
    }
    
    patch_data = {
        "nodes": [
            {
                "id": "node_lr1",
                "type": "Paper",
                "label": "LightRAG",
                "provenance": provenance
            },
            {
                "id": "node_lr2",
                "type": "Claim",
                "label": "Graph structures improve retrieval",
                "provenance": provenance
            }
        ],
        "edges": [
            {
                "source": "node_lr1",
                "target": "node_lr2",
                "type": "MAKES_CLAIM",
                "provenance": provenance
            }
        ]
    }
    
    patch = GraphPatch(**patch_data)
    assert patch.nodes[1].type == NodeType.CLAIM
    assert patch.edges[0].type == EdgeType.MAKES_CLAIM

def test_valid_graph_patch_mind_the_query():
    """Test schema with a valid graph patch similar to Mind the Query demo."""
    provenance = {
        "paper_id": "mind_the_query",
        "chunk_id": "chunk_099",
        "text_span": "we discuss the validation of generated graph queries on benchmark datasets",
    }
    
    patch_data = {
        "nodes": [
            {
                "id": "node_mtq1",
                "type": "Paper",
                "label": "Mind the Query",
                "provenance": provenance
            },
            {
                "id": "node_mtq2",
                "type": "Benchmark",
                "label": "Graph Query Validation Dataset",
                "provenance": provenance
            }
        ],
        "edges": [
            {
                "source": "node_mtq1",
                "target": "node_mtq2",
                "type": "EVALUATES_ON",
                "provenance": provenance
            }
        ]
    }
    
    patch = GraphPatch(**patch_data)
    assert patch.nodes[1].type == NodeType.BENCHMARK
    assert patch.edges[0].type == EdgeType.EVALUATES_ON

def test_unsupported_node_type():
    """Test that unsupported node types are rejected."""
    provenance = {
        "paper_id": "test_paper",
        "chunk_id": "test_chunk",
        "text_span": "test span"
    }
    
    with pytest.raises(ValidationError):
        KGNode(**{
            "id": "node_1",
            "type": "UnsupportedType",
            "label": "Test",
            "provenance": provenance
        })

def test_unsupported_edge_type():
    """Test that unsupported edge types are rejected."""
    provenance = {
        "paper_id": "test_paper",
        "chunk_id": "test_chunk",
        "text_span": "test span"
    }
    
    with pytest.raises(ValidationError):
        KGEdge(**{
            "source": "node_1",
            "target": "node_2",
            "type": "UNSUPPORTED_RELATION",
            "provenance": provenance
        })

def test_missing_provenance():
    """Test that missing provenance is rejected."""
    with pytest.raises(ValidationError):
        KGNode(**{
            "id": "node_1",
            "type": "Paper",
            "label": "Test"
            # Missing provenance
        })
        
    with pytest.raises(ValidationError):
        KGEdge(**{
            "source": "node_1",
            "target": "node_2",
            "type": "PROPOSES"
            # Missing provenance
        })

def test_missing_required_provenance_fields():
    """Test that provenance requires specific fields."""
    with pytest.raises(ValidationError):
        Provenance(**{
            "paper_id": "test_paper",
            "chunk_id": "test_chunk"
            # Missing text_span
        })
        
    with pytest.raises(ValidationError):
        Provenance(**{
            "paper_id": "test_paper",
            "text_span": "test span"
            # Missing chunk_id
        })
        
    with pytest.raises(ValidationError):
        Provenance(**{
            "chunk_id": "test_chunk",
            "text_span": "test span"
            # Missing paper_id
        })


def test_validation_report_for_valid_patch():
    patch_data = {
        "nodes": [
            {
                "id": "paper:lightrag",
                "type": "Paper",
                "label": "LightRAG",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "We propose LightRAG.",
                },
            },
            {
                "id": "claim:lightrag_retrieval",
                "type": "Claim",
                "label": "Graph structures improve retrieval",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "Graph structures improve retrieval by capturing relationships between entities.",
                },
            },
            {
                "id": "evidence:lightrag_001",
                "type": "Evidence",
                "label": "retrieval evidence",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "capturing relationships between entities",
                },
            },
        ],
        "edges": [
            {
                "source": "paper:lightrag",
                "target": "claim:lightrag_retrieval",
                "type": "MAKES_CLAIM",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "We propose LightRAG.",
                },
            },
            {
                "source": "evidence:lightrag_001",
                "target": "claim:lightrag_retrieval",
                "type": "SUPPORTED_BY",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "capturing relationships between entities",
                },
            },
        ],
    }

    report = validate_graph_patch(
        patch_data,
        chunk_text_by_id={
            "chunk_001": (
                "We propose LightRAG. "
                "Graph structures improve retrieval by capturing relationships between entities."
            )
        },
    )

    assert isinstance(report, ValidationReport)
    assert report.is_valid is True
    assert report.errors == []
    assert report.warnings == []
    assert report.node_count == 3
    assert report.edge_count == 2


def test_validation_reports_missing_edge_references_and_duplicate_ids():
    patch_data = {
        "nodes": [
            {
                "id": "node_1",
                "type": "Paper",
                "label": "AutoGraph-R1",
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "chunk_001",
                    "text_span": "AutoGraph-R1",
                },
            },
            {
                "id": "node_1",
                "type": "Method",
                "label": "RL framework",
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "chunk_001",
                    "text_span": "reinforcement learning",
                },
            },
        ],
        "edges": [
            {
                "source": "node_1",
                "target": "missing_node",
                "type": "PROPOSES",
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "chunk_001",
                    "text_span": "proposes",
                },
            }
        ],
    }

    report = validate_graph_patch(patch_data)

    assert report.is_valid is False
    assert "Duplicate node ID detected: 'node_1'." in report.errors
    assert "Edge 'PROPOSES' references missing target node 'missing_node'." in report.errors
    assert report.node_count == 2
    assert report.edge_count == 1


def test_validation_reports_missing_or_empty_provenance_fields():
    patch_data = {
        "nodes": [
            {
                "id": "claim_1",
                "type": "Claim",
                "label": "Useful claim",
                "provenance": {
                    "paper_id": "  ",
                    "chunk_id": "chunk_001",
                    "text_span": " ",
                },
            }
        ],
        "edges": [],
    }

    report = validate_graph_patch(patch_data)

    assert report.is_valid is False
    assert "Node 'claim_1' is missing a non-empty provenance.paper_id." in report.errors
    assert "Node 'claim_1' is missing a non-empty provenance.text_span." in report.errors


def test_validation_reports_unmatched_source_span_and_isolated_evidence():
    patch_data = {
        "nodes": [
            {
                "id": "evidence_1",
                "type": "Evidence",
                "label": "retrieval evidence",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "not in source text",
                },
            }
        ],
        "edges": [],
    }

    report = validate_graph_patch(
        patch_data,
        chunk_text_by_id={"chunk_001": "This chunk contains different text entirely."},
    )

    assert report.is_valid is False
    assert (
        "Node 'evidence_1' provenance.text_span is not a direct substring of chunk 'chunk_001'."
        in report.errors
    )
    assert (
        "Evidence node 'evidence_1' is isolated from any SUPPORTED_BY edge."
        in report.warnings
    )


def test_validation_reports_word_level_junk_nodes():
    patch_data = {
        "nodes": [
            {
                "id": "claim_1",
                "type": "Claim",
                "label": "Graph",
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "chunk_001",
                    "text_span": "Graph",
                },
            }
        ],
        "edges": [],
    }

    report = validate_graph_patch(patch_data)

    assert report.is_valid is False
    assert "Node 'claim_1' has a likely word-level junk label 'Graph'." in report.errors
