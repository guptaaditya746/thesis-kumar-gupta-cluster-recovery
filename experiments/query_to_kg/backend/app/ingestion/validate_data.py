"""
Dataset validation script for Milestone 1.

M1-WI-11 goal:
- Confirm the Milestone 1 dataset is complete and internally consistent.
- Validate manifest, structured paper JSON files, and base chunk JSONL.
- Do not generate data here.
- Do not parse PDFs here.
- Do not build KG, SPARQL, retrieval, or UI logic here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.ingestion.schemas import BaseChunk, PaperDocument


EXPECTED_PAPER_COUNT = 3
MIN_SECTION_COUNT = 4
MIN_CHUNK_CHARS = 100

DATA_DIR = Path("backend/app/data")
MANIFEST_PATH = DATA_DIR / "manifest.json"
BASE_CHUNKS_PATH = DATA_DIR / "chunks" / "base_chunks.jsonl"


def load_json_file(path: Path) -> Any:
    """
    Load a JSON file and return the parsed data.
    """
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON file: {path}: {error}") from error


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict[str, Any]]:
    """
    Load the Milestone 1 manifest.
    """
    data = load_json_file(path)

    if not isinstance(data, list):
        raise ValueError(f"Manifest must be a list, found: {type(data).__name__}")

    return data


def paper_document_from_dict(data: dict[str, Any]) -> PaperDocument:
    """
    Load a PaperDocument from raw JSON data.

    Project uses Pydantic v2.
    """
    return PaperDocument.model_validate(data)


def base_chunk_from_dict(data: dict[str, Any]) -> BaseChunk:
    """
    Load a BaseChunk from raw JSON data.

    Project uses Pydantic v2.
    """
    return BaseChunk.model_validate(data)


def load_structured_paper(path: Path) -> PaperDocument:
    """
    Load one structured paper JSON file.
    """
    data = load_json_file(path)

    if not isinstance(data, dict):
        raise ValueError(f"Structured paper JSON must be an object: {path}")

    return paper_document_from_dict(data)


def load_chunks_jsonl(path: Path = BASE_CHUNKS_PATH) -> list[BaseChunk]:
    """
    Load base chunks from JSONL.

    Each non-empty line must be valid JSON and must validate as a BaseChunk.
    """
    if not path.exists():
        raise FileNotFoundError(f"Chunks JSONL file not found: {path}")

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
                    f"Invalid JSON in {path} on line {line_number}: {error}"
                ) from error

            try:
                chunk = base_chunk_from_dict(data)
            except Exception as error:
                raise ValueError(
                    f"Invalid BaseChunk in {path} on line {line_number}: {error}"
                ) from error

            chunks.append(chunk)

    return chunks


def validate_manifest(
    manifest: list[dict[str, Any]],
    errors: list[str],
) -> None:
    """
    Validate manifest-level requirements.
    """
    if len(manifest) != EXPECTED_PAPER_COUNT:
        errors.append(
            f"Expected exactly {EXPECTED_PAPER_COUNT} papers in manifest, "
            f"found {len(manifest)}."
        )

    seen_paper_ids: set[str] = set()

    for index, record in enumerate(manifest, start=1):
        if not isinstance(record, dict):
            errors.append(f"Manifest record {index} is not an object.")
            continue

        paper_id = record.get("paper_id")
        title = record.get("title")
        structured_json = record.get("structured_json")

        if not paper_id:
            errors.append(f"Manifest record {index} is missing paper_id.")
        elif paper_id in seen_paper_ids:
            errors.append(f"Duplicate paper_id in manifest: {paper_id}")
        else:
            seen_paper_ids.add(paper_id)

        if not title:
            errors.append(f"Manifest record {index} is missing title.")

        if not structured_json:
            errors.append(f"Manifest record {index} is missing structured_json.")
        else:
            structured_path = Path(structured_json)
            if not structured_path.exists():
                errors.append(
                    f"Structured paper JSON does not exist for "
                    f"{paper_id or f'record {index}'}: {structured_path}"
                )


def load_structured_papers_from_manifest(
    manifest: list[dict[str, Any]],
    errors: list[str],
) -> list[PaperDocument]:
    """
    Load all structured paper JSON files referenced by the manifest.
    """
    papers: list[PaperDocument] = []

    for record in manifest:
        structured_json = record.get("structured_json")
        paper_id = record.get("paper_id", "unknown_paper")

        if not structured_json:
            continue

        path = Path(structured_json)

        try:
            paper = load_structured_paper(path)
        except Exception as error:
            errors.append(
                f"Failed to load structured paper for {paper_id} from {path}: {error}"
            )
            continue

        papers.append(paper)

    return papers


def has_introduction_section(paper: PaperDocument) -> bool:
    """
    Return True if the paper has a section whose title looks like Introduction.
    """
    return any(
        "introduction" in section.title.lower()
        for section in paper.sections
    )


def validate_structured_papers(
    papers: list[PaperDocument],
    errors: list[str],
) -> None:
    """
    Validate structured PaperDocument objects.
    """
    if len(papers) != EXPECTED_PAPER_COUNT:
        errors.append(
            f"Expected exactly {EXPECTED_PAPER_COUNT} structured papers, "
            f"found {len(papers)}."
        )

    for paper in papers:
        paper_id = paper.metadata.paper_id
        title = paper.metadata.title

        if not paper_id:
            errors.append("A structured paper is missing metadata.paper_id.")

        if not title:
            errors.append(
                f"Structured paper {paper_id or '<unknown>'} is missing metadata.title."
            )

        if not paper.abstract and not has_introduction_section(paper):
            errors.append(
                f"Paper {paper_id or '<unknown>'} has neither abstract nor "
                f"introduction section."
            )

        if len(paper.sections) < MIN_SECTION_COUNT:
            errors.append(
                f"Paper {paper_id or '<unknown>'} has fewer than "
                f"{MIN_SECTION_COUNT} sections: {len(paper.sections)}."
            )

        seen_section_ids: set[str] = set()

        for section in paper.sections:
            if not section.section_id:
                errors.append(f"Paper {paper_id} has a section missing section_id.")

            if section.section_id in seen_section_ids:
                errors.append(
                    f"Paper {paper_id} has duplicate section_id: {section.section_id}"
                )
            else:
                seen_section_ids.add(section.section_id)

            if not section.title:
                errors.append(
                    f"Paper {paper_id} section {section.section_id} is missing title."
                )

            if not section.text or not section.text.strip():
                errors.append(
                    f"Paper {paper_id} section {section.section_id} has empty text."
                )


def validate_chunks(
    chunks: list[BaseChunk],
    papers: list[PaperDocument],
    errors: list[str],
) -> None:
    """
    Validate chunk-level requirements.
    """
    if not chunks:
        errors.append("No chunks loaded from base_chunks.jsonl.")
        return

    expected_paper_ids = {
        paper.metadata.paper_id
        for paper in papers
        if paper.metadata.paper_id
    }

    chunk_paper_ids = {
        chunk.paper_id
        for chunk in chunks
        if chunk.paper_id
    }

    missing_paper_ids = expected_paper_ids - chunk_paper_ids
    unexpected_paper_ids = chunk_paper_ids - expected_paper_ids

    if missing_paper_ids:
        errors.append(
            "Chunks are missing papers: "
            + ", ".join(sorted(missing_paper_ids))
        )

    if unexpected_paper_ids:
        errors.append(
            "Chunks contain unexpected paper IDs: "
            + ", ".join(sorted(unexpected_paper_ids))
        )

    valid_section_ids = {
        section.section_id
        for paper in papers
        for section in paper.sections
    }

    seen_chunk_ids: set[str] = set()
    duplicate_chunk_ids: set[str] = set()

    for chunk in chunks:
        if not chunk.chunk_id:
            errors.append("A chunk is missing chunk_id.")
        elif chunk.chunk_id in seen_chunk_ids:
            duplicate_chunk_ids.add(chunk.chunk_id)
        else:
            seen_chunk_ids.add(chunk.chunk_id)

        if not chunk.paper_id:
            errors.append(f"Chunk {chunk.chunk_id or '<unknown>'} is missing paper_id.")

        if not chunk.section_id:
            errors.append(
                f"Chunk {chunk.chunk_id or '<unknown>'} is missing section_id."
            )
        elif chunk.section_id not in valid_section_ids:
            errors.append(
                f"Chunk {chunk.chunk_id} references unknown section_id: "
                f"{chunk.section_id}"
            )

        if not chunk.raw_text or not chunk.raw_text.strip():
            errors.append(f"Chunk {chunk.chunk_id or '<unknown>'} has empty raw_text.")
        elif len(chunk.raw_text) < MIN_CHUNK_CHARS:
            errors.append(
                f"Chunk {chunk.chunk_id} has fewer than "
                f"{MIN_CHUNK_CHARS} characters."
            )

    if duplicate_chunk_ids:
        errors.append(
            "Duplicate chunk_id values found: "
            + ", ".join(sorted(duplicate_chunk_ids))
        )

    chunk_ids = {
        chunk.chunk_id
        for chunk in chunks
        if chunk.chunk_id
    }

    for chunk in chunks:
        if chunk.previous_chunk_id and chunk.previous_chunk_id not in chunk_ids:
            errors.append(
                f"Chunk {chunk.chunk_id} has invalid previous_chunk_id: "
                f"{chunk.previous_chunk_id}"
            )

        if chunk.next_chunk_id and chunk.next_chunk_id not in chunk_ids:
            errors.append(
                f"Chunk {chunk.chunk_id} has invalid next_chunk_id: "
                f"{chunk.next_chunk_id}"
            )


def count_chunks_by_paper(chunks: list[BaseChunk]) -> dict[str, int]:
    """
    Return paper_id to chunk count.
    """
    counts: dict[str, int] = {}

    for chunk in chunks:
        counts[chunk.paper_id] = counts.get(chunk.paper_id, 0) + 1

    return counts


def validate_dataset() -> tuple[list[str], list[PaperDocument], list[BaseChunk]]:
    """
    Run all Milestone 1 validation checks.
    """
    errors: list[str] = []

    try:
        manifest = load_manifest()
    except Exception as error:
        return [f"Failed to load manifest: {error}"], [], []

    validate_manifest(manifest, errors)

    papers = load_structured_papers_from_manifest(manifest, errors)
    validate_structured_papers(papers, errors)

    try:
        chunks = load_chunks_jsonl()
    except Exception as error:
        errors.append(f"Failed to load base_chunks.jsonl: {error}")
        chunks = []

    validate_chunks(chunks, papers, errors)

    return errors, papers, chunks


def print_summary(
    papers: list[PaperDocument],
    chunks: list[BaseChunk],
    errors: list[str],
) -> None:
    """
    Print a readable validation summary.
    """
    print(f"Loaded papers: {len(papers)}")
    print(f"Structured papers: {len(papers)}")
    print(f"Total chunks: {len(chunks)}")

    chunk_counts = count_chunks_by_paper(chunks)

    for paper in papers:
        paper_id = paper.metadata.paper_id
        title = paper.metadata.title
        section_count = len(paper.sections)
        chunk_count = chunk_counts.get(paper_id, 0)

        print()
        print(f"Paper: {title}")
        print(f"Paper ID: {paper_id}")
        print(f"Sections: {section_count}")
        print(f"Chunks: {chunk_count}")

    print()

    if errors:
        print("Validation: FAILED")
        print()
        print("Errors:")

        for error in errors:
            print(f"- {error}")
    else:
        print("Validation: PASSED")


def main() -> None:
    """
    CLI entry point.

    Run from project root:

        PYTHONPATH=. python -m backend.app.ingestion.validate_data
    """
    errors, papers, chunks = validate_dataset()
    print_summary(papers, chunks, errors)

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
