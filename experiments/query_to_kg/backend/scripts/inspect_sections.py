import json
from pathlib import Path

from backend.app.ingestion.section_parser import parse_sections_from_file


MANIFEST_PATH = Path("backend/app/data/manifest.json")


def load_manifest() -> list[dict]:
    """Load paper records from the Milestone 1 manifest."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def main() -> None:
    papers = load_manifest()

    for paper in papers:
        paper_id = paper["paper_id"]
        parsed_text_path = Path(paper["parsed_text"])

        print(f"\nPaper: {paper_id}")

        sections = parse_sections_from_file(
            paper_id=paper_id,
            parsed_text_path=parsed_text_path,
        )

        for section in sections:
            print(
                f"{section.order:02d} | "
                f"level={section.level} | "
                f"{section.title} | "
                f"{len(section.text)} chars"
            )

        print(f"Total sections: {len(sections)}")


if __name__ == "__main__":
    main()
