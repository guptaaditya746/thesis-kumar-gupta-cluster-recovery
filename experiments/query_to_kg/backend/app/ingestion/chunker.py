"""
Section-aware base chunker for Milestone 1.

M1-WI-09 goal:
- Read structured PaperDocument objects
- Split each section into BaseChunk objects
- Preserve paper, section, and ordering provenance
- Never mix papers
- Never mix sections


M1-WI-10 goal:
- Write generated chunks to backend/app/data/chunks/base_chunks.jsonl
- Store one valid JSON object per line
- Preserve stable chunk IDs and previous/next links
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.ingestion.schemas import BaseChunk, PaperDocument, Section

BASE_CHUNKS_PATH = Path("backend/app/data/chunks/base_chunks.jsonl")

DEFAULT_CHUNK_SIZE_TOKENS = 1000
DEFAULT_CHUNK_OVERLAP_TOKENS = 120
MIN_CHUNK_CHARS = 100


def slugify(value: str) -> str:
    """
    Convert text into a stable lowercase ID fragment.
    """
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "section"


def model_to_dict(model: Any) -> dict[str, Any]:
    """
    Serialize Pydantic v1 or v2 models into dictionaries.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")

    if hasattr(model, "dict"):
        return model.dict()

    raise TypeError(f"Unsupported model type: {type(model)}")


def paper_document_from_dict(data: dict[str, Any]) -> PaperDocument:
    """
    Load a PaperDocument from raw JSON data.

    """
    
    return PaperDocument.model_validate(data)

def base_chunk_from_dict(data: dict[str, Any]) -> BaseChunk:
    """
    Load a BaseChunk from raw JSON data.
    """
    return BaseChunk.model_validate(data)


def load_structured_paper(path: str | Path) -> PaperDocument:
    """
    Load one structured paper JSON file.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Structured paper JSON not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    return paper_document_from_dict(data)


def load_structured_papers(paths: list[str | Path]) -> list[PaperDocument]:
    """
    Load multiple structured paper JSON files.
    """
    return [load_structured_paper(path) for path in paths]


def split_text_into_token_windows(
    text: str,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """
    Split text into overlapping token windows.

    This uses whitespace tokens for now. That is enough for Milestone 1.
    Later, this can be replaced with a model tokenizer if needed.
    """
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be greater than 0.")

    if chunk_overlap_tokens < 0:
        raise ValueError("chunk_overlap_tokens cannot be negative.")

    if chunk_overlap_tokens >= chunk_size_tokens:
        raise ValueError("chunk_overlap_tokens must be smaller than chunk_size_tokens.")

    normalized_text = text.strip()

    if not normalized_text:
        return []

    tokens = normalized_text.split()

    if len(tokens) <= chunk_size_tokens:
        return [normalized_text]

    chunks: list[str] = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size_tokens, len(tokens))
        chunk_text = " ".join(tokens[start:end]).strip()

        if chunk_text:
            chunks.append(chunk_text)

        if end == len(tokens):
            break

        start = end - chunk_overlap_tokens

    return chunks


def make_chunk_id(
    paper_id: str,
    section: Section,
    chunk_index: int,
) -> str:
    """
    Create a stable, readable chunk ID.
    """
    section_slug = slugify(section.title)

    return f"{paper_id}_{section_slug}_{chunk_index:04d}"


def chunk_section(
    paper: PaperDocument,
    section: Section,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
) -> list[BaseChunk]:
    """
    Split one section into BaseChunk objects.

    Important:
    - This function only sees one section.
    - Therefore, it cannot accidentally cross section boundaries.
    """
    paper_id = paper.metadata.paper_id
    paper_title = paper.metadata.title

    raw_windows = split_text_into_token_windows(
        text=section.text,
        chunk_size_tokens=chunk_size_tokens,
        chunk_overlap_tokens=chunk_overlap_tokens,
    )

    chunks: list[BaseChunk] = []

    for local_index, raw_text in enumerate(raw_windows, start=1):
        raw_text = raw_text.strip()

        if len(raw_text) < min_chunk_chars:
            continue

        chunk_id = make_chunk_id(
            paper_id=paper_id,
            section=section,
            chunk_index=local_index,
        )

        chunk = BaseChunk(
            chunk_id=chunk_id,
            paper_id=paper_id,
            paper_title=paper_title,
            section_id=section.section_id,
            section_title=section.title,
            chunk_index=local_index,
            raw_text=raw_text,
            page_start=section.page_start,
            page_end=section.page_end,
            char_start=None,
            char_end=None,
            previous_chunk_id=None,
            next_chunk_id=None,
            source_type="section_text",
        )

        chunks.append(chunk)

    link_neighbor_chunks(chunks)

    return chunks


def link_neighbor_chunks(chunks: list[BaseChunk]) -> None:
    """
    Add previous_chunk_id and next_chunk_id links within one section only.
    """
    for index, chunk in enumerate(chunks):
        previous_chunk = chunks[index - 1] if index > 0 else None
        next_chunk = chunks[index + 1] if index < len(chunks) - 1 else None

        chunk.previous_chunk_id = previous_chunk.chunk_id if previous_chunk else None
        chunk.next_chunk_id = next_chunk.chunk_id if next_chunk else None


def chunk_paper(
    paper: PaperDocument,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
) -> list[BaseChunk]:
    """
    Create chunks for one paper.

    This loops section by section, so chunks never cross section boundaries.
    """
    all_chunks: list[BaseChunk] = []

    for section in paper.sections:
        section_chunks = chunk_section(
            paper=paper,
            section=section,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            min_chunk_chars=min_chunk_chars,
        )

        all_chunks.extend(section_chunks)

    return all_chunks


def chunk_papers(
    papers: list[PaperDocument],
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
) -> list[BaseChunk]:
    """
    Create chunks for multiple papers.

    This processes one paper at a time, so chunks never cross paper boundaries.
    """
    all_chunks: list[BaseChunk] = []

    for paper in papers:
        paper_chunks = chunk_paper(
            paper=paper,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            min_chunk_chars=min_chunk_chars,
        )

        all_chunks.extend(paper_chunks)

    ensure_unique_chunk_ids(all_chunks)

    return all_chunks


def ensure_unique_chunk_ids(chunks: list[BaseChunk]) -> None:
    """
    Fail fast if duplicate chunk IDs are created.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()

    for chunk in chunks:
        if chunk.chunk_id in seen:
            duplicates.add(chunk.chunk_id)

        seen.add(chunk.chunk_id)

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(f"Duplicate chunk IDs found: {duplicate_list}")


def ensure_valid_chunk_links(chunks: list[BaseChunk]) -> None:
    """
    Fail fast if previous_chunk_id or next_chunk_id points to a missing chunk.

    This is intentionally small. Full dataset validation belongs to M1-WI-11.
    """
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}

    for chunk in chunks:
        if chunk.previous_chunk_id is not None:
            previous_chunk = chunks_by_id.get(chunk.previous_chunk_id)

            if previous_chunk is None:
                raise ValueError(
                    f"Invalid previous_chunk_id for {chunk.chunk_id}: "
                    f"{chunk.previous_chunk_id}"
                )

            if previous_chunk.next_chunk_id != chunk.chunk_id:
                raise ValueError(
                    f"Broken backward link: {chunk.chunk_id} points back to "
                    f"{previous_chunk.chunk_id}, but that chunk does not point forward to it."
                )

        if chunk.next_chunk_id is not None:
            next_chunk = chunks_by_id.get(chunk.next_chunk_id)

            if next_chunk is None:
                raise ValueError(
                    f"Invalid next_chunk_id for {chunk.chunk_id}: "
                    f"{chunk.next_chunk_id}"
                )

            if next_chunk.previous_chunk_id != chunk.chunk_id:
                raise ValueError(
                    f"Broken forward link: {chunk.chunk_id} points forward to "
                    f"{next_chunk.chunk_id}, but that chunk does not point back to it."
                )


def write_chunks_jsonl(
    chunks: list[BaseChunk],
    output_path: str | Path = BASE_CHUNKS_PATH,
) -> Path:
    """
    Write BaseChunk objects to a JSONL file.

    Each line is one complete JSON object representing one chunk.
    """
    if not chunks:
        raise ValueError("No chunks provided. Refusing to write empty base_chunks.jsonl.")

    ensure_unique_chunk_ids(chunks)
    ensure_valid_chunk_links(chunks)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            chunk_data = model_to_dict(chunk)
            file.write(json.dumps(chunk_data, ensure_ascii=False) + "\n")

    return output_path


def load_chunks_jsonl(path: str | Path = BASE_CHUNKS_PATH) -> list[BaseChunk]:
    """
    Reload chunks from a JSONL file.

    This is useful for smoke tests and will also help M1-WI-11 validation.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Chunks JSONL not found: {path}")

    chunks: list[BaseChunk] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}: {error}"
                ) from error

            chunks.append(base_chunk_from_dict(data))

    ensure_unique_chunk_ids(chunks)
    ensure_valid_chunk_links(chunks)

    return chunks


def summarize_chunks(chunks: list[BaseChunk]) -> dict[str, int]:
    """
    Return a simple paper_id to chunk count summary.
    """
    summary: dict[str, int] = {}

    for chunk in chunks:
        summary[chunk.paper_id] = summary.get(chunk.paper_id, 0) + 1

    return summary




def main() -> None:
    """
    Manual smoke test.

    Run from project root:

        PYTHONPATH=. python -m backend.app.ingestion.chunker
    """
    structured_dir = Path("backend/app/data/structured_papers")

    structured_paths = [
        structured_dir / "lightrag.json",
        structured_dir / "autograph_r1.json",
        structured_dir / "mind_the_query.json",
    ]

    papers = load_structured_papers(structured_paths)

    chunks = chunk_papers(papers)
    output_path = write_chunks_jsonl(chunks)

    reloaded_chunks = load_chunks_jsonl(output_path)

    print(f"Loaded papers: {len(papers)}")
    print(f"Created chunks: {len(chunks)}")
    print(f"Reloaded chunks: {len(reloaded_chunks)}")
    print(f"Output: {output_path}")
    print()

    for paper_id, count in summarize_chunks(chunks).items():
        print(f"{paper_id}: {count} chunks")

    if chunks:
        sample = chunks[0]
        print()
        print("Sample chunk:")
        print(json.dumps(model_to_dict(sample), indent=2, ensure_ascii=False)[:1200])


if __name__ == "__main__":
    main()
