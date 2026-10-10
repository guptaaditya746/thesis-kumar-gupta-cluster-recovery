"""
Pydantic data models for Milestone 1.

These schemas define the basic shape of the paper dataset:
metadata, sections, structured paper documents, and base chunks.

The goal of this file is not to parse PDFs or create chunks.
It only defines what valid data should look like.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    """
    Basic bibliographic and file metadata for one research paper.

    This model keeps paper-level information separate from the actual
    parsed content. Other objects can use paper_id to link back to this
    metadata.
    """

    paper_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    source_pdf: Optional[str] = None


class Section(BaseModel):
    """
    A single logical section from a paper.

    Sections preserve the reading order and give later chunks a stable
    source location. Page numbers are optional because early parsed text
    may not always include reliable page information.
    """

    section_id: str
    paper_id: str
    title: str
    level: int
    order: int
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class PaperDocument(BaseModel):
    """
    A structured representation of one parsed paper.

    This is the main document object produced after loading parsed text
    and splitting it into sections.
    """

    metadata: PaperMetadata
    abstract: Optional[str] = None
    sections: List[Section] = Field(default_factory=list)
    references: List[Dict[str, Any]] = Field(default_factory=list)


class BaseChunk(BaseModel):
    """
    A section-aware text chunk used for later retrieval and provenance.

    Each chunk belongs to exactly one paper and one section. The previous
    and next chunk fields make it possible to reconstruct local context
    without mixing different papers or sections.
    """

    chunk_id: str
    paper_id: str
    paper_title: str
    section_id: str
    section_title: str
    chunk_index: int

    raw_text: str

    page_start: Optional[int] = None
    page_end: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None

    source_type: str = "section_text"
