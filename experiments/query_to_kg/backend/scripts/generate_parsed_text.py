from __future__ import annotations

import argparse
from pathlib import Path 

from backend.app.ingestion.parsed_text_generator import (
    generate_parsed_text_for_paper,
    load_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "backend" / "app" / "data" / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate parsed text files for Milestone 1 papers."
    )

    parser.add_argument(
        "--parser",
        choices=["liteparse", "marker", "docling", "pymupdf"],
        default=None,
        help="Preferred parser to try first. Fallbacks still run if it fails.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    papers = load_manifest(MANIFEST_PATH)

    print(f"Loaded manifest records: {len(papers)}")

    successes = 0

    for paper in papers:
        ok = generate_parsed_text_for_paper(
            paper=paper,
            project_root=PROJECT_ROOT,
            preferred_parser=args.parser,
        )

        if ok:
            successes += 1

    print("")
    print(f"Parsed text files ready: {successes}/{len(papers)}")

    if successes != len(papers):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
