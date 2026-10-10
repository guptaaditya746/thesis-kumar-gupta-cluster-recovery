"""
Paper loader for Milestone 1.

This module reads the paper manifest and validates that expected
input files exist before later ingestion steps use them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "backend" / "app" / "data" / "manifest.json"


@dataclass(frozen=True)
class PaperRecord:
    """
    One paper entry loaded from manifest.json.

    Paths are resolved to absolute Path objects so later code can use them
    safely regardless of the current working directory.
    """

    paper_id: str
    title: str
    year: int | None
    source_pdf: Path
    parsed_text_path: Path | None
    structured_json_path: Path | None


def _resolve_path(path_value: str | None) -> Path | None:
    """
    Resolve a path from the manifest.

    Manifest paths are expected to be relative to the project root, but
    absolute paths are also accepted.
    """

    if not path_value:
        return None

    path = Path(path_value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def _get_first_available(entry: dict[str, Any], keys: list[str]) -> str | None:
    """
    Return the first non-empty value found for a list of possible keys.

    This keeps the loader tolerant of small manifest naming differences like:
    - parsed_text
    - parsed_text_path
    - structured_json
    - structured_json_path
    """

    for key in keys:
        value = entry.get(key)
        if value:
            return str(value)

    return None


def load_papers(manifest_path: Path | str = DEFAULT_MANIFEST_PATH) -> list[PaperRecord]:
    """
    Load all paper records from manifest.json and validate file paths.

    Required:
    - manifest.json must exist
    - each paper must have paper_id, title, and source_pdf
    - each source_pdf must exist

    Optional:
    - parsed text path is checked only when present
    - structured JSON path is loaded when present but not required to exist yet
    """

    manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as file:
        manifest_data = json.load(file)

    if not isinstance(manifest_data, list):
        raise ValueError("Manifest must be a JSON list of paper records.")

    records: list[PaperRecord] = []
    errors: list[str] = []

    for index, entry in enumerate(manifest_data):
        if not isinstance(entry, dict):
            errors.append(f"Manifest entry #{index} is not an object.")
            continue

        paper_id = entry.get("paper_id")
        title = entry.get("title")
        year = entry.get("year")

        source_pdf_value = _get_first_available(entry, ["source_pdf", "source_pdf_path"])
        parsed_text_value = _get_first_available(
            entry,
            ["parsed_text_path", "parsed_text"],
        )
        structured_json_value = _get_first_available(
            entry,
            ["structured_json_path", "structured_json"],
        )

        if not paper_id:
            errors.append(f"Manifest entry #{index} is missing required field: paper_id")
            continue

        if not title:
            errors.append(f"Paper {paper_id} is missing required field: title")

        if not source_pdf_value:
            errors.append(f"Paper {paper_id} is missing required field: source_pdf")
            continue

        source_pdf = _resolve_path(source_pdf_value)
        parsed_text_path = _resolve_path(parsed_text_value)
        structured_json_path = _resolve_path(structured_json_value)

        if source_pdf is None or not source_pdf.exists():
            errors.append(f"Paper {paper_id} PDF not found: {source_pdf}")

        if parsed_text_path is not None and not parsed_text_path.exists():
            errors.append(f"Paper {paper_id} parsed text not found: {parsed_text_path}")

        records.append(
            PaperRecord(
                paper_id=str(paper_id),
                title=str(title),
                year=int(year) if year is not None else None,
                source_pdf=source_pdf,
                parsed_text_path=parsed_text_path,
                structured_json_path=structured_json_path,
            )
        )

    if errors:
        error_message = "Paper loader validation failed:\n" + "\n".join(
            f"- {error}" for error in errors
        )
        raise FileNotFoundError(error_message)

    return records


if __name__ == "__main__":
    papers = load_papers()

    print(f"Loaded {len(papers)} paper records:")
    for paper in papers:
        print(f"- {paper.paper_id}: {paper.title}")
        print(f"  PDF: {paper.source_pdf}")
        print(f"  Parsed text: {paper.parsed_text_path}")
