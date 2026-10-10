from typing import Any

from pydantic import BaseModel, Field


class EvidenceRecord(BaseModel):
    paper_id: str
    paper_title: str | None = None
    section_title: str | None = None
    chunk_id: str
    text_span: str


class TraceStep(BaseModel):
    step: str
    details: Any


class AnswerResponse(BaseModel):
    answer: str
    query: str
    query_result: dict[str, Any]
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
