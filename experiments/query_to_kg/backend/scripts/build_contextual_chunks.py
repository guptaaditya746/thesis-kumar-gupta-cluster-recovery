from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.app.retrieval.schemas import ContextualChunk
from backend.app.retrieval.contextualizer import (
    CHUNKS_PATH,
    MANIFEST_PATH,
    OUTPUT_PATH,
    STRUCTURED_PAPERS_DIR,
    assemble_contextualization_inputs,
    generate_contextualized_chunks,
    write_contextualized_chunks,
)

# Initialize a module-level logger
logger = logging.getLogger(__name__)


def validate_output_file(
    *,
    output_path: Path,
    base_raw_text_by_chunk_id: dict[str, str],
) -> None:
    if not output_path.exists():
        raise FileNotFoundError(f"Output file does not exist: {output_path}")

    seen_chunk_ids: set[str] = set()
    row_count = 0

    with output_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL at {output_path}, line {line_number}"
                ) from exc

            chunk = ContextualChunk.model_validate(data)

            if chunk.chunk_id in seen_chunk_ids:
                raise ValueError(f"Duplicate chunk_id in output: {chunk.chunk_id} on line {line_number}")

            seen_chunk_ids.add(chunk.chunk_id)

            expected_raw_text = base_raw_text_by_chunk_id.get(chunk.chunk_id)
            if expected_raw_text is None:
                raise ValueError(f"Output contains unknown chunk_id not present in base chunks: {chunk.chunk_id}")

            if chunk.raw_text != expected_raw_text:
                raise ValueError(f"raw_text was unexpectedly modified for chunk_id={chunk.chunk_id}")

            if not chunk.index_text.strip():
                raise ValueError(f"Empty index_text generated for chunk_id={chunk.chunk_id}")

            if chunk.raw_text not in chunk.index_text:
                raise ValueError(
                    f"index_text does not contain original raw_text for chunk_id={chunk.chunk_id}"
                )

            if not (3 <= len(chunk.retrieval_tags) <= 8):
                raise ValueError(
                    f"Expected 3-8 retrieval tags for chunk_id={chunk.chunk_id}, "
                    f"got {len(chunk.retrieval_tags)}"
                )

            row_count += 1

    if row_count != len(base_raw_text_by_chunk_id):
        raise ValueError(
            f"Output row count mismatch: expected {len(base_raw_text_by_chunk_id)} rows, "
            f"but wrote {row_count} rows."
        )


def main() -> None:
    # Setup logging format to include timestamps and severity levels
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    logger.info("Assembling contextualization inputs...")
    load_result = assemble_contextualization_inputs(
        chunks_path=CHUNKS_PATH,
        manifest_path=MANIFEST_PATH,
        structured_papers_dir=STRUCTURED_PAPERS_DIR,
    )

    base_raw_text_by_chunk_id = {
        record.chunk_id: record.current_chunk_text
        for record in load_result.records
    }

    logger.info(f"Generating contextualized chunks for {load_result.total_chunks} inputs...")
    contextualized_chunks = generate_contextualized_chunks(
        load_result.records,
        fallback_on_error=True,
    )

    logger.info("Writing contextualized chunks to disk...")
    write_contextualized_chunks(
        chunks=contextualized_chunks,
        output_path=OUTPUT_PATH,
    )

    logger.info("Validating output file integrity...")
    validate_output_file(
        output_path=OUTPUT_PATH,
        base_raw_text_by_chunk_id=base_raw_text_by_chunk_id,
    )

    # Replaced print statements with standard logging
    logger.info(f"Loaded base chunks: {load_result.total_chunks}")
    logger.info(f"Written contextual chunks: {len(contextualized_chunks)}")
    logger.info(f"Output path: {OUTPUT_PATH}")
    logger.info("Validation: PASSED ✅")


if __name__ == "__main__":
    main()
