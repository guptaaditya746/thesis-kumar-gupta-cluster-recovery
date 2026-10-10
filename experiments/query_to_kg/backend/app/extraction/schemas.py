from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class NodeType(str, Enum):
    PAPER = "Paper"
    METHOD = "Method"
    DATASET = "Dataset"
    TASK = "Task"
    CLAIM = "Claim"
    EVIDENCE = "Evidence"
    LIMITATION = "Limitation"
    METRIC = "Metric"
    BENCHMARK = "Benchmark"

class EdgeType(str, Enum):
    PROPOSES = "PROPOSES"
    ADDRESSES_TASK = "ADDRESSES_TASK"
    USES_METHOD = "USES_METHOD"
    EVALUATES_ON = "EVALUATES_ON"
    REPORTS_METRIC = "REPORTS_METRIC"
    MAKES_CLAIM = "MAKES_CLAIM"
    SUPPORTED_BY = "SUPPORTED_BY"
    HAS_LIMITATION = "HAS_LIMITATION"
    DESCRIBES = "DESCRIBES"
    COMPARES_WITH = "COMPARES_WITH"
    FROM_PAPER = "FROM_PAPER"
    FROM_CHUNK = "FROM_CHUNK"

class Provenance(BaseModel):
    """
    Strict provenance mapping back to the original source evidence.
    Every text span in the graph patch must come directly from raw_text.
    """
    paper_id: str
    chunk_id: str
    text_span: str = Field(description="The exact text span from the chunk's raw_text acting as evidence.")
    paper_title: Optional[str] = None
    section_title: Optional[str] = None

class KGNode(BaseModel):
    id: str = Field(description="Unique identifier for the node in the query-specific graph patch.")
    type: NodeType = Field(description="The semantic type of the node.")
    label: str = Field(description="A concise, human-readable label for the node.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Flexible properties for the node.")
    provenance: Provenance = Field(description="The strict provenance tracing back to source text.")

class KGEdge(BaseModel):
    source: str = Field(description="The ID of the source node.")
    target: str = Field(description="The ID of the target node.")
    type: EdgeType = Field(description="The relationship type between source and target.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Flexible properties for the edge.")
    provenance: Provenance = Field(description="The strict provenance tracing back to source text.")

class GraphPatch(BaseModel):
    """
    A query-specific graph patch generated from retrieved chunks.
    This is not a full corpus KG, but a localized evidence graph.
    """
    nodes: List[KGNode] = Field(default_factory=list, description="List of extracted nodes.")
    edges: List[KGEdge] = Field(default_factory=list, description="List of extracted edges.")


class ValidationReport(BaseModel):
    """Structured validation result for a query-specific graph patch."""

    is_valid: bool = Field(description="Whether the graph patch passed validation without errors.")
    errors: List[str] = Field(default_factory=list, description="Hard validation failures.")
    warnings: List[str] = Field(default_factory=list, description="Repairable issues or unverifiable conditions.")
    node_count: int = Field(default=0, description="Number of nodes observed in the graph patch.")
    edge_count: int = Field(default=0, description="Number of edges observed in the graph patch.")
