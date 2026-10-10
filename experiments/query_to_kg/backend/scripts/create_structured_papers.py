"""
Create structured paper JSON files for M1-WI-08.

Run from the project root:

    python backend/scripts/create_structured_papers.py

Expected outputs:
    backend/app/data/structured_papers/lightrag.json
    backend/app/data/structured_papers/autograph_r1.json
    backend/app/data/structured_papers/mind_the_query.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ingestion.structured_paper_builder import (  # noqa: E402
    build_structured_paper,
    get_structured_json_path,
    write_structured_paper,
)


MANIFEST_PATH = PROJECT_ROOT / "backend/app/data/manifest.json"


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> list[dict[str, Any]]:
    """
    Load the Milestone 1 paper manifest.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Manifest must be a JSON list of paper records.")

    if len(data) != 3:
        raise ValueError(f"Expected exactly 3 paper records, found {len(data)}.")

    return data


def validate_manifest_record(record: dict[str, Any]) -> None:
    """
    Validate minimum fields needed for M1-WI-08.
    """
    required_fields = ["paper_id", "title"]

    for field in required_fields:
        if not record.get(field):
            raise ValueError(f"Manifest record is missing required field: {field}")

    has_parsed_text = bool(record.get("parsed_text") or record.get("parsed_text_path"))
    has_structured_json = bool(
        record.get("structured_json") or record.get("structured_json_path")
    )

    if not has_parsed_text:
        raise ValueError(
            f"Manifest record for '{record['paper_id']}' is missing "
            "'parsed_text' or 'parsed_text_path'."
        )

    if not has_structured_json:
        raise ValueError(
            f"Manifest record for '{record['paper_id']}' is missing "
            "'structured_json' or 'structured_json_path'."
        )


def main() -> None:
    """
    Build and write all structured paper JSON files.
    """
    manifest = load_manifest()

    print("Creating structured paper JSON files...")
    print(f"Manifest: {MANIFEST_PATH}")

    written_files: list[Path] = []

    for record in manifest:
        validate_manifest_record(record)

        paper = build_structured_paper(
            paper_record=record,
            project_root=PROJECT_ROOT,
        )

        output_path = get_structured_json_path(
            paper_record=record,
            project_root=PROJECT_ROOT,
        )

        written_path = write_structured_paper(
            paper=paper,
            output_path=output_path,
            project_root=PROJECT_ROOT,
        )

        written_files.append(written_path)

        abstract_status = "yes" if paper.abstract else "no"
        references_status = "yes" if paper.references else "no"

        print(
            f"✓ {paper.metadata.paper_id}: "
            f"sections={len(paper.sections)}, "
            f"abstract={abstract_status}, "
            f"references={references_status}, "
            f"output={written_path.relative_to(PROJECT_ROOT)}"
        )

    if len(written_files) != 3:
        raise RuntimeError(f"Expected to write 3 files, wrote {len(written_files)}.")

    print()
    print("M1-WI-08 complete.")
    print("Structured JSON files written:")

    for path in written_files:
        print(f"- {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
