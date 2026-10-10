# models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------

class NodeType(BaseModel):
    label: str
    key: str                        # unique property name, e.g. "doi" or "name"
    properties: List[str]           # allowed properties


class RelType(BaseModel):
    type: str
    from_label: str
    to_label: str
    properties: List[str] = []


class GraphSchema(BaseModel):
    nodes: List[NodeType]
    relationships: List[RelType]
    normalization_rules: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extraction models
# ---------------------------------------------------------------------------

class NodeRef(BaseModel):
    label: str
    key: str
    value: str


class ExtractedNode(BaseModel):
    ref: NodeRef
    properties: Dict[str, Any] = {}


class ExtractedRel(BaseModel):
    type: str
    from_ref: NodeRef
    to_ref: NodeRef
    properties: Dict[str, Any] = {}


class Extraction(BaseModel):
    document_id: str
    nodes: List[ExtractedNode]
    relationships: List[ExtractedRel]
