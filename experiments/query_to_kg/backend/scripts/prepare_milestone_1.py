"""
Milestone 1 preparation script.

M1-WI-12 goal:
- Provide one command that prepares the Milestone 1 dataset.
- Confirm required inputs exist.
- Load structured paper JSON files.
- Generate base chunks.
- Write backend/app/data/chunks/base_chunks.jsonl.
- Run dataset validation.
- Print a clear summary.

Run from project root:

    python backend/scripts/prepare_milestone_1.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.app.ingestion.chunker import (  # noqa: E402
    BASE_CHUNKS_PATH,
    chunk_papers,
    load_structured_papers,
    summarize_chunks,
    write_chunks_jsonl,
)
from backend.app.ingestion.validate_data import validate_dataset  # noqa: E402


DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"


def project_path(path_value: str | Path) -> Path:
    """
    Convert a project-relative path into an absolute path.
    """
    path = Path(path_value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict[str, Any]]:
    """
    Load backend/app/data/manifest.json.
    """
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError(f"Manifest must be a list, found: {type(data).__name__}")

    return data


def confirm_manifest_inputs(manifest: list[dict[str, Any]]) -> None:
    """
    Confirm files referenced by the manifest exist.

    This script does not parse PDFs. Parsed text generation belongs to the
    parser script created earlier in Milestone 1.
    """
    for record in manifest:
        paper_id = record.get("paper_id", "<unknown>")
        source_pdf = record.get("source_pdf")
        parsed_text = record.get("parsed_text")
        structured_json = record.get("structured_json")

        if not source_pdf:
            raise ValueError(f"Manifest record {paper_id} is missing source_pdf.")

        if not parsed_text:
            raise ValueError(f"Manifest record {paper_id} is missing parsed_text.")

        if not structured_json:
            raise ValueError(f"Manifest record {paper_id} is missing structured_json.")

        source_pdf_path = project_path(source_pdf)
        parsed_text_path = project_path(parsed_text)
        structured_json_path = project_path(structured_json)

        if not source_pdf_path.exists():
            raise FileNotFoundError(
                f"Raw PDF for {paper_id} not found: {source_pdf_path}"
            )

        if not parsed_text_path.exists():
            raise FileNotFoundError(
                f"Parsed text for {paper_id} not found: {parsed_text_path}"
            )

        if not structured_json_path.exists():
            raise FileNotFoundError(
                f"Structured paper JSON for {paper_id} not found: "
                f"{structured_json_path}"
            )


def get_structured_json_paths(manifest: list[dict[str, Any]]) -> list[Path]:
    """
    Return absolute structured paper JSON paths from the manifest.
    """
    return [
        project_path(record["structured_json"])
        for record in manifest
    ]


def print_preparation_summary(
    manifest: list[dict[str, Any]],
    chunk_counts: dict[str, int],
    total_chunks: int,
    validation_errors: list[str],
) -> None:
    """
    Print a clear Milestone 1 preparation summary.
    """
    title_by_paper_id = {
        record["paper_id"]: record.get("title", record["paper_id"])
        for record in manifest
    }

    print(f"Loaded papers: {len(manifest)}")
    print()

    for paper_id, title in title_by_paper_id.items():
        print(f"Paper: {title}")
        print(f"Chunks: {chunk_counts.get(paper_id, 0)}")
        print()

    print(f"Total chunks: {total_chunks}")

    if validation_errors:
        print("Validation: FAILED")
        print()
        print("Errors:")

        for error in validation_errors:
            print(f"- {error}")
    else:
        print("Validation: PASSED")

    print(f"Output: {BASE_CHUNKS_PATH}")


def main() -> None:
    """
    Run the full Milestone 1 data preparation flow.
    """
    manifest = load_manifest()
    confirm_manifest_inputs(manifest)

    structured_json_paths = get_structured_json_paths(manifest)
    papers = load_structured_papers(structured_json_paths)

    chunks = chunk_papers(papers)
    write_chunks_jsonl(chunks, BASE_CHUNKS_PATH)

    validation_errors, _validated_papers, validated_chunks = validate_dataset()

    chunk_counts = summarize_chunks(validated_chunks)

    print_preparation_summary(
        manifest=manifest,
        chunk_counts=chunk_counts,
        total_chunks=len(validated_chunks),
        validation_errors=validation_errors,
    )

    if validation_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
