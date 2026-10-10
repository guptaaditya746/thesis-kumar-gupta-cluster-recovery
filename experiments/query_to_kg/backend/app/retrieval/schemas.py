"""

"""


from pydantic import BaseModel, Field
from typing import Optional, Literal



class ContextualizationInput(BaseModel):
    chunk_id: str
    paper_id: str
    paper_title: str
    abstract: str

    section_id: str
    section_title: str
    chunk_index: int

    previous_chunk_id: Optional[str] = None
    previous_chunk_text: Optional[str] = None

    current_chunk_text: str

    next_chunk_id: Optional[str] = None
    next_chunk_text: Optional[str] = None


class ContextualChunk(BaseModel):
    
    chunk_id: str 
    paper_id: str 
    paper_title: str 
    section_id: str 
    section_title: str 
    chunk_index: int 


    raw_text: str 
    contextual_summary: str 
    index_text: str 


    retrieval_tags: list[str] = Field(default_factory = list) 


    page_start: Optional[int] = None 
    page_end: Optional[int] = None 
    char_start: Optional[int] = None
    char_end: Optional[int] = None 


    previous_chunk_id: Optional[str] = None 
    next_chunk_id: Optional[str] = None

    source_type: Literal[
        "abstract",
        "section_text",
        "table",
        "figure_caption",
        "reference",
        "appendix"
    ] = "section_text"


class RetrievedChunk(BaseModel):
    chunk_id: str
    paper_id: str
    paper_title: str
    section_id: str
    section_title: str

    raw_text: str
    contextual_summary: str

    score: float
    retrieval_method: str
    rank: int

    page_start: Optional[int] = None
    page_end: Optional[int] = None


