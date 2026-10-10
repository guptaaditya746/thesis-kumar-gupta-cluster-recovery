from __future__ import annotations

import json
import logging
import time
import concurrent.futures
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from tqdm import tqdm

from backend.app.llm_config import API_KEY, CHAT_API_BASE, CHAT_MODEL
from backend.app.retrieval.schemas import (
    ContextualizationInput,
    ContextualChunk,
)

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("backend/app/prompts/contextual_chunk_prompt.txt")
OUTPUT_PATH = Path("backend/app/data/chunks/contextualized_chunks.jsonl")
CHUNKS_PATH = Path("backend/app/data/chunks/base_chunks.jsonl")
MANIFEST_PATH = Path("backend/app/data/manifest.json")
STRUCTURED_PAPERS_DIR = Path("backend/app/data/structured_papers")

MIN_RETRIEVAL_TAGS = 3
MAX_RETRIEVAL_TAGS = 8
MAX_CONCURRENT_WORKERS = 10  # Adjust based on your vLLM server capacity

KNOWN_RETRIEVAL_TERMS = [
    "LightRAG",
    "AutoGraph-R1",
    "Mind the Query",
]

try:
    from litellm import completion
except ImportError as exc:
    raise RuntimeError("LiteLLM is not installed; please run `pip install litellm`") from exc


class PaperMetadata(BaseModel):
    paper_id: str
    title: str
    abstract: str = ""


class ContextualizationLoadResult(BaseModel):
    records: list[ContextualizationInput]
    total_chunks: int
    missing_abstracts: int = 0
    missing_previous_refs: int = 0
    missing_next_refs: int = 0
    cross_paper_neighbor_refs: int = 0


def load_contextual_chunk_prompt(prompt_path: Path = PROMPT_PATH) -> str:
    if not prompt_path.exists():
        raise FileNotFoundError(f"Contextual chunk prompt not found: {prompt_path}")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Contextual chunk prompt is empty: {prompt_path}")

    return prompt


def format_optional_text(value: str | None) -> str:
    return value.strip() if value else "[Not available]"


def build_summary_prompt(template: str, record: ContextualizationInput) -> str:
    return template.format(
        paper_title=record.paper_title,
        section_title=record.section_title,
        abstract=format_optional_text(record.abstract),
        previous_chunk_text=format_optional_text(record.previous_chunk_text),
        current_chunk_text=record.current_chunk_text.strip(),
        next_chunk_text=format_optional_text(record.next_chunk_text),
    )


def validate_contextual_summary(summary: str | None, chunk_id: str) -> str:
    if not isinstance(summary, str):
        raise ValueError(
            f"Contextual summary for chunk_id={chunk_id} must be a string, "
            f"got {type(summary).__name__}"
        )

    cleaned = summary.strip()

    if not cleaned:
        raise ValueError(f"Empty contextual summary for chunk_id={chunk_id}")

    sentence_count = cleaned.count(".") + cleaned.count("?") + cleaned.count("!")

    if sentence_count > 5:
        logger.warning(
            "Contextual summary may be too long for chunk_id=%s: %s sentence markers",
            chunk_id,
            sentence_count,
        )

    return cleaned


def call_summary_model(prompt: str, max_retries: int = 3) -> str:
    """Calls the LLM with exponential backoff for transient errors."""
    for attempt in range(max_retries):
        try:
            response = completion(
                model=CHAT_MODEL,
                api_base=CHAT_API_BASE,
                api_key=API_KEY,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return only the final contextual summary. "
                            "Do not include thinking, reasoning, analysis, markdown, or bullet points."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=512,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )

            message = response.choices[0].message
            content = message.content

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(f"Model returned empty content: {response.model_dump()}")

            cleaned = content.strip()

            if cleaned.lower().startswith("thinking process"):
                raise RuntimeError(f"Model returned reasoning instead of summary: {cleaned[:300]}")

            return cleaned

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
            time.sleep(2 ** attempt)


def fallback_summary(record: ContextualizationInput) -> str:
    return (
        f"This chunk appears in the section '{record.section_title}' "
        f"of the paper '{record.paper_title}'. "
        "It should be interpreted using the current chunk text and its immediate neighboring chunks."
    )


def normalize_tag(tag: str) -> str:
    return " ".join(tag.strip().split())


def add_tag(tags: list[str], tag: str) -> None:
    cleaned = normalize_tag(tag)
    if not cleaned:
        return
    existing = {item.lower() for item in tags}
    if cleaned.lower() not in existing:
        tags.append(cleaned)


def generate_retrieval_tags(
    *,
    paper_title: str,
    section_title: str,
    raw_text: str,
    contextual_summary: str,
) -> list[str]:
    searchable_text = "\n".join(
        [
            paper_title,
            section_title,
            raw_text,
            contextual_summary,
        ]
    ).lower()

    tags: list[str] = []

    for known_term in KNOWN_RETRIEVAL_TERMS:
        if known_term.lower() in searchable_text:
            add_tag(tags, known_term)

    add_tag(tags, paper_title)
    add_tag(tags, section_title)

    candidate_terms = [
        "knowledge graph", "retrieval", "query", "question answering",
        "graph construction", "entity extraction", "relation extraction",
        "reasoning", "baseline", "evaluation", "benchmark", "ablation",
        "prompting", "large language model", "LLM", "RAG", "BM25",
        "vector retrieval",
    ]

    for term in candidate_terms:
        if term.lower() in searchable_text:
            add_tag(tags, term)

    return tags[:MAX_RETRIEVAL_TAGS]


def build_index_text(chunk: ContextualChunk) -> str:
    tags = ", ".join(chunk.retrieval_tags)
    return (
        f"Paper: {chunk.paper_title}\n"
        f"Section: {chunk.section_title}\n"
        f"Context: {chunk.contextual_summary}\n"
        f"Tags: {tags}\n"
        f"Source chunk:\n"
        f"{chunk.raw_text}"
    )


def validate_retrieval_enrichment(chunk: ContextualChunk) -> None:
    if not (MIN_RETRIEVAL_TAGS <= len(chunk.retrieval_tags) <= MAX_RETRIEVAL_TAGS):
        raise ValueError(
            f"Chunk {chunk.chunk_id} must have "
            f"{MIN_RETRIEVAL_TAGS}-{MAX_RETRIEVAL_TAGS} retrieval tags, "
            f"got {len(chunk.retrieval_tags)}"
        )

    for tag in chunk.retrieval_tags:
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError(f"Chunk {chunk.chunk_id} has invalid retrieval tag: {tag!r}")

    if not chunk.index_text.strip():
        raise ValueError(f"Chunk {chunk.chunk_id} has empty index_text")

    if chunk.raw_text not in chunk.index_text:
        raise ValueError(f"Chunk {chunk.chunk_id} index_text does not contain raw_text")


def build_contextual_chunk(
    record: ContextualizationInput,
    contextual_summary: str,
) -> ContextualChunk:
    summary = validate_contextual_summary(
        contextual_summary,
        chunk_id=record.chunk_id,
    )
    raw_text = record.current_chunk_text

    retrieval_tags = generate_retrieval_tags(
        paper_title=record.paper_title,
        section_title=record.section_title,
        raw_text=raw_text,
        contextual_summary=summary,
    )

    chunk = ContextualChunk(
        chunk_id=record.chunk_id,
        paper_id=record.paper_id,
        paper_title=record.paper_title,
        section_id=record.section_id,
        section_title=record.section_title,
        chunk_index=record.chunk_index,
        raw_text=raw_text,
        contextual_summary=summary,
        index_text="",
        retrieval_tags=retrieval_tags,
        previous_chunk_id=record.previous_chunk_id,
        next_chunk_id=record.next_chunk_id,
    )

    chunk.index_text = build_index_text(chunk)
    validate_retrieval_enrichment(chunk)

    return chunk


def generate_contextualized_chunks(
    records: list[ContextualizationInput],
    prompt_path: Path = PROMPT_PATH,
    fallback_on_error: bool = False,
) -> list[ContextualChunk]:
    template = load_contextual_chunk_prompt(prompt_path)

    contextualized: list[ContextualChunk] = []
    failed_chunk_ids: list[str] = []
    fallback_chunk_ids: list[str] = []

    def process_record(record: ContextualizationInput) -> tuple[ContextualChunk | None, str | None, bool]:
        """Worker function for concurrent execution."""
        try:
            prompt = build_summary_prompt(template, record)
            summary = call_summary_model(prompt)
            chunk = build_contextual_chunk(record, summary)
            return chunk, None, False
        except Exception as e:
            logger.debug("Failed contextual summary for chunk_id=%s: %s", record.chunk_id, e)
            if fallback_on_error:
                summary = fallback_summary(record)
                chunk = build_contextual_chunk(record, summary)
                return chunk, record.chunk_id, True
            return None, record.chunk_id, False

    # Execute calls concurrently
    logger.info("Starting concurrent contextualization for %d chunks...", len(records))
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
        futures = {executor.submit(process_record, r): r for r in records}
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(records), desc="Contextualizing"):
            chunk, failed_id, used_fallback = future.result()
            
            if failed_id:
                if used_fallback and chunk:
                    contextualized.append(chunk)
                    fallback_chunk_ids.append(failed_id)
                else:
                    failed_chunk_ids.append(failed_id)
            elif chunk:
                contextualized.append(chunk)

    if failed_chunk_ids and not fallback_on_error:
        raise RuntimeError(
            f"Contextual summary generation failed for {len(failed_chunk_ids)} chunks: {failed_chunk_ids}"
        )

    # Sort chunks back into original order by chunk_index or ID to maintain consistency
    contextualized.sort(key=lambda c: (c.paper_id, c.chunk_index))

    logger.info("Contextualized chunks generated: %s", len(contextualized))
    logger.info("Failed summaries: %s", len(failed_chunk_ids))
    logger.info("Fallback summaries: %s", len(fallback_chunk_ids))

    return contextualized


def write_contextualized_chunks(
    chunks: list[ContextualChunk],
    output_path: Path = OUTPUT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} in {path}") from exc

            if not isinstance(record, dict):
                raise ValueError(f"Expected JSON object on line {line_number} in {path}")
            records.append(record)
    return records


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_chunk_text(chunk: dict[str, Any]) -> str:
    text = chunk.get("raw_text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Chunk {chunk.get('chunk_id')} is missing raw_text")
    return text


def build_chunk_lookup(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    chunk_by_id: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError(f"Found chunk without valid chunk_id: {chunk}")
        if chunk_id in chunk_by_id:
            raise ValueError(f"Duplicate chunk_id found: {chunk_id}")
        chunk_by_id[chunk_id] = chunk
    return chunk_by_id


def load_structured_paper_metadata(structured_papers_dir: Path) -> dict[str, PaperMetadata]:
    metadata_by_paper_id: dict[str, PaperMetadata] = {}
    if not structured_papers_dir.exists():
        return metadata_by_paper_id

    for path in sorted(structured_papers_dir.glob("*.json")):
        data = load_json(path)
        paper_id = data.get("paper_id") or data.get("id") or path.stem

        if not isinstance(paper_id, str) or not paper_id:
            continue

        title = data.get("title") or data.get("paper_title") or paper_id
        abstract = data.get("abstract") or data.get("abstract_text") or ""

        if not isinstance(title, str):
            title = paper_id
        if not isinstance(abstract, str):
            abstract = ""

        metadata_by_paper_id[paper_id] = PaperMetadata(
            paper_id=paper_id,
            title=title,
            abstract=abstract,
        )
    return metadata_by_paper_id


def load_manifest_metadata(manifest_path: Path) -> dict[str, PaperMetadata]:
    metadata_by_paper_id: dict[str, PaperMetadata] = {}
    if not manifest_path.exists():
        return metadata_by_paper_id

    data = load_json(manifest_path)
    candidates: list[tuple[str, dict[str, Any]]] = []

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            paper_id = item.get("paper_id") or item.get("id")
            if isinstance(paper_id, str):
                candidates.append((paper_id, item))

    elif isinstance(data, dict):
        papers = data.get("papers")
        if isinstance(papers, list):
            for item in papers:
                if not isinstance(item, dict):
                    continue
                paper_id = item.get("paper_id") or item.get("id")
                if isinstance(paper_id, str):
                    candidates.append((paper_id, item))
        elif isinstance(papers, dict):
            for paper_id, item in papers.items():
                if isinstance(paper_id, str) and isinstance(item, dict):
                    candidates.append((paper_id, item))
        else:
            for paper_id, item in data.items():
                if isinstance(paper_id, str) and isinstance(item, dict):
                    candidates.append((paper_id, item))
    else:
        raise ValueError(f"Expected JSON object or array in {manifest_path}")

    for paper_id, item in candidates:
        title = item.get("title") or item.get("paper_title") or paper_id
        abstract = item.get("abstract") or item.get("abstract_text") or ""

        if not isinstance(title, str):
            title = paper_id
        if not isinstance(abstract, str):
            abstract = ""

        metadata_by_paper_id[paper_id] = PaperMetadata(
            paper_id=paper_id,
            title=title,
            abstract=abstract,
        )
    return metadata_by_paper_id


def resolve_paper_metadata(
    paper_id: str,
    structured_metadata: dict[str, PaperMetadata],
    manifest_metadata: dict[str, PaperMetadata],
) -> PaperMetadata:
    structured = structured_metadata.get(paper_id)
    manifest = manifest_metadata.get(paper_id)

    title = paper_id
    abstract = ""

    if manifest is not None:
        title = manifest.title or title
        abstract = manifest.abstract or abstract

    if structured is not None:
        title = structured.title or title
        abstract = structured.abstract or abstract

    return PaperMetadata(
        paper_id=paper_id,
        title=title,
        abstract=abstract,
    )


def resolve_neighbor_text(
    *,
    chunk: dict[str, Any],
    neighbor_field: str,
    chunk_by_id: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None, bool, bool]:
    neighbor_id = chunk.get(neighbor_field)
    if neighbor_id is None:
        return None, None, False, False

    if not isinstance(neighbor_id, str) or not neighbor_id:
        return None, None, True, False

    neighbor = chunk_by_id.get(neighbor_id)
    if neighbor is None:
        return neighbor_id, None, True, False

    current_paper_id = chunk.get("paper_id")
    neighbor_paper_id = neighbor.get("paper_id")

    if current_paper_id != neighbor_paper_id:
        return neighbor_id, None, False, True

    return neighbor_id, get_chunk_text(neighbor), False, False


def assemble_contextualization_inputs(
    *,
    chunks_path: Path,
    manifest_path: Path,
    structured_papers_dir: Path,
) -> ContextualizationLoadResult:
    chunks = load_jsonl(chunks_path)
    chunk_by_id = build_chunk_lookup(chunks)

    structured_metadata = load_structured_paper_metadata(structured_papers_dir)
    manifest_metadata = load_manifest_metadata(manifest_path)

    records: list[ContextualizationInput] = []

    missing_abstracts = 0
    missing_previous_refs = 0
    missing_next_refs = 0
    cross_paper_neighbor_refs = 0

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        paper_id = chunk.get("paper_id")
        section_id = chunk.get("section_id")
        section_title = chunk.get("section_title")
        chunk_index = chunk.get("chunk_index")

        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError(f"Chunk is missing valid chunk_id: {chunk}")
        if not isinstance(paper_id, str) or not paper_id:
            raise ValueError(f"Chunk {chunk_id} is missing valid paper_id")
        if not isinstance(section_id, str) or not section_id:
            raise ValueError(f"Chunk {chunk_id} is missing valid section_id")
        if not isinstance(section_title, str) or not section_title:
            raise ValueError(f"Chunk {chunk_id} is missing valid section_title")
        if not isinstance(chunk_index, int):
            raise ValueError(f"Chunk {chunk_id} is missing valid chunk_index")

        paper_metadata = resolve_paper_metadata(
            paper_id=paper_id,
            structured_metadata=structured_metadata,
            manifest_metadata=manifest_metadata,
        )

        if not paper_metadata.abstract:
            missing_abstracts += 1

        (
            previous_chunk_id,
            previous_chunk_text,
            previous_missing,
            previous_cross_paper,
        ) = resolve_neighbor_text(
            chunk=chunk,
            neighbor_field="previous_chunk_id",
            chunk_by_id=chunk_by_id,
        )

        (
            next_chunk_id,
            next_chunk_text,
            next_missing,
            next_cross_paper,
        ) = resolve_neighbor_text(
            chunk=chunk,
            neighbor_field="next_chunk_id",
            chunk_by_id=chunk_by_id,
        )

        if previous_missing:
            missing_previous_refs += 1
        if next_missing:
            missing_next_refs += 1
        if previous_cross_paper:
            cross_paper_neighbor_refs += 1
        if next_cross_paper:
            cross_paper_neighbor_refs += 1

        records.append(
            ContextualizationInput(
                chunk_id=chunk_id,
                paper_id=paper_id,
                paper_title=paper_metadata.title,
                abstract=paper_metadata.abstract,
                section_id=section_id,
                section_title=section_title,
                chunk_index=chunk_index,
                previous_chunk_id=previous_chunk_id,
                previous_chunk_text=previous_chunk_text,
                current_chunk_text=get_chunk_text(chunk),
                next_chunk_id=next_chunk_id,
                next_chunk_text=next_chunk_text,
            )
        )

    return ContextualizationLoadResult(
        records=records,
        total_chunks=len(chunks),
        missing_abstracts=missing_abstracts,
        missing_previous_refs=missing_previous_refs,
        missing_next_refs=missing_next_refs,
        cross_paper_neighbor_refs=cross_paper_neighbor_refs,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    load_result = assemble_contextualization_inputs(
        chunks_path=CHUNKS_PATH,
        manifest_path=MANIFEST_PATH,
        structured_papers_dir=STRUCTURED_PAPERS_DIR,
    )

    contextualized_chunks = generate_contextualized_chunks(
        load_result.records,
        fallback_on_error=True,
    )

    write_contextualized_chunks(contextualized_chunks)

    print(f"\n--- Processing Summary ---")
    print(f"Loaded chunks: {load_result.total_chunks}")
    print(f"Missing abstracts: {load_result.missing_abstracts}")
    print(f"Missing previous refs: {load_result.missing_previous_refs}")
    print(f"Missing next refs: {load_result.missing_next_refs}")
    print(f"Cross-paper neighbor refs: {load_result.cross_paper_neighbor_refs}")
    print(f"Contextualized chunks written: {len(contextualized_chunks)}")
    print(f"Output: {OUTPUT_PATH}")
