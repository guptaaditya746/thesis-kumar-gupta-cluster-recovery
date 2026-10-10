import re
from typing import List
from pydantic import BaseModel, Field
from backend.app.extraction.schemas import NodeType, EdgeType

class QueryIntent(BaseModel):
    """Structured representation of the parsed query intent."""
    intent_type: str = Field(description="The classified intent of the query (e.g., method_proposal).")
    target_entities: List[str] = Field(default_factory=list, description="Extracted target entities or concepts.")
    needed_node_types: List[NodeType] = Field(default_factory=list, description="Node types required to fulfill this intent.")
    needed_edge_types: List[EdgeType] = Field(default_factory=list, description="Edge types required to fulfill this intent.")

def analyze_query(query: str) -> QueryIntent:
    """
    Analyzes a user question using lightweight rules to map it to a specific graph extraction intent.
    This informs the downstream LLM extractor about which node and edge types to focus on.
    """
    q_lower = query.lower()
    
    # Rule 1: Benchmark / Validation (e.g., Mind the Query)
    if any(kw in q_lower for kw in ["validation", "benchmark", "evaluates", "dataset"]):
        target_match = re.search(r"validation of (.*?)(?:\?|$)", q_lower)
        targets = [target_match.group(1).strip()] if target_match else []
        return QueryIntent(
            intent_type="benchmark_evaluation",
            target_entities=targets,
            needed_node_types=[NodeType.PAPER, NodeType.BENCHMARK, NodeType.METRIC, NodeType.TASK],
            needed_edge_types=[EdgeType.EVALUATES_ON, EdgeType.REPORTS_METRIC, EdgeType.ADDRESSES_TASK]
        )
        
    # Rule 2: Claim / Evidence (e.g., LightRAG)
    if any(kw in q_lower for kw in ["argues", "claim", "evidence", "prove", "shows that"]):
        target_match = re.search(r"argues that (.*?)(?:\?|$)", q_lower)
        targets = [target_match.group(1).strip()] if target_match else []
        return QueryIntent(
            intent_type="claim_evidence",
            target_entities=targets,
            needed_node_types=[NodeType.PAPER, NodeType.CLAIM, NodeType.EVIDENCE],
            needed_edge_types=[EdgeType.MAKES_CLAIM, EdgeType.SUPPORTED_BY]
        )
        
    # Rule 4: Limitation
    if any(kw in q_lower for kw in ["limitation", "weakness", "fails", "struggles"]):
        return QueryIntent(
            intent_type="limitation",
            target_entities=[],
            needed_node_types=[NodeType.PAPER, NodeType.LIMITATION, NodeType.METHOD],
            needed_edge_types=[EdgeType.HAS_LIMITATION]
        )
        
    # Rule 5: Comparison
    if any(kw in q_lower for kw in ["compares", "better than", "outperforms", "versus"]):
        return QueryIntent(
            intent_type="comparison",
            target_entities=[],
            needed_node_types=[NodeType.PAPER, NodeType.METHOD, NodeType.BENCHMARK],
            needed_edge_types=[EdgeType.COMPARES_WITH, EdgeType.EVALUATES_ON]
        )
        
    # Rule 3: Method / Proposal (e.g., AutoGraph-R1)
    if any(kw in q_lower for kw in ["proposes", "method", "approach"]):
        target_match = re.search(r"proposes a (.*?)(?:\?|$)", q_lower)
        targets = [target_match.group(1).strip()] if target_match else []
        return QueryIntent(
            intent_type="method_proposal",
            target_entities=targets,
            needed_node_types=[NodeType.PAPER, NodeType.METHOD, NodeType.TASK],
            needed_edge_types=[EdgeType.PROPOSES, EdgeType.ADDRESSES_TASK]
        )
        
    # Generic Fallback
    return QueryIntent(
        intent_type="generic_extraction",
        target_entities=[],
        needed_node_types=[NodeType.PAPER, NodeType.METHOD, NodeType.CLAIM, NodeType.DATASET],
        needed_edge_types=[EdgeType.PROPOSES, EdgeType.MAKES_CLAIM, EdgeType.EVALUATES_ON]
    )
