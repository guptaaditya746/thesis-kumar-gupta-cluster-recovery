import pytest
from backend.app.extraction.query_understanding import analyze_query
from backend.app.extraction.schemas import NodeType, EdgeType

def test_autograph_r1_question():
    """Test the AutoGraph-R1 demo question maps to method/proposal intent."""
    query = "Which paper proposes a reinforcement-learning approach for knowledge graph construction?"
    intent = analyze_query(query)
    
    assert intent.intent_type == "method_proposal"
    assert "reinforcement-learning approach for knowledge graph construction" in intent.target_entities
    assert NodeType.METHOD in intent.needed_node_types
    assert EdgeType.PROPOSES in intent.needed_edge_types

def test_lightrag_question():
    """Test the LightRAG demo question maps to claim/evidence intent."""
    query = "Which paper argues that graph structures improve retrieval by capturing relationships between entities?"
    intent = analyze_query(query)
    
    assert intent.intent_type == "claim_evidence"
    assert "graph structures improve retrieval by capturing relationships between entities" in intent.target_entities
    assert NodeType.CLAIM in intent.needed_node_types
    assert EdgeType.MAKES_CLAIM in intent.needed_edge_types

def test_mind_the_query_question():
    """Test the Mind the Query demo question maps to benchmark/evaluation intent."""
    query = "Which paper discusses validation of generated graph queries?"
    intent = analyze_query(query)
    
    assert intent.intent_type == "benchmark_evaluation"
    assert "generated graph queries" in intent.target_entities
    assert NodeType.BENCHMARK in intent.needed_node_types
    assert EdgeType.EVALUATES_ON in intent.needed_edge_types

def test_limitation_question():
    """Test a question about limitations maps correctly."""
    query = "What is the main limitation of this approach?"
    intent = analyze_query(query)
    
    assert intent.intent_type == "limitation"
    assert NodeType.LIMITATION in intent.needed_node_types
    assert EdgeType.HAS_LIMITATION in intent.needed_edge_types

def test_comparison_question():
    """Test a question about comparison maps correctly."""
    query = "How does this method perform versus the baseline?"
    intent = analyze_query(query)
    
    assert intent.intent_type == "comparison"
    assert EdgeType.COMPARES_WITH in intent.needed_edge_types

def test_unknown_question_fallback():
    """Test an unknown question safely falls back to a generic extraction intent."""
    query = "Tell me about the universe."
    intent = analyze_query(query)
    
    assert intent.intent_type == "generic_extraction"
    assert len(intent.needed_node_types) > 0
    assert len(intent.needed_edge_types) > 0
