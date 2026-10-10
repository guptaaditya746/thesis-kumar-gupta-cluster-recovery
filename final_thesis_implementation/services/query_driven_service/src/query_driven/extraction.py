from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .clients import TextClient
from .config import ServiceConfig
from .io import read_json, safe_id, write_json
from .logging import get_logger
from .pattern import parse_graph_pattern
from .prompts import EXTRACT_RELATION_PROMPT


def _pattern_text(pattern: dict[str, Any]) -> str:
    parsed = pattern.get("pattern") or parse_graph_pattern(str(pattern.get("response", "")))
    lines = ["Entity types: [" + ", ".join(parsed.get("entity_types", [])) + "]"]
    for rel in parsed.get("relationships", []):
        lines.append(f"{rel['source_type']} -> {rel['target_type']}: {rel['description']}")
    return "\n".join(lines)


async def run_extraction_stage(
    cfg: ServiceConfig,
    questions: list[dict[str, Any]],
    texts_by_id: dict[str, dict[str, Any]],
    client: TextClient,
) -> None:
    logger = get_logger(stage="extraction")
    semaphore = asyncio.Semaphore(cfg.runtime.concurrency)

    async def extract_doc(question: dict[str, Any], doc_id: str, graph_pattern: str) -> None:
        qid = safe_id(question[cfg.dataset.qid_field])
        safe_doc = safe_id(doc_id)
        path = cfg.runtime.output_root / "extraction" / qid / f"{safe_doc}.json"
        if cfg.runtime.resume and path.exists() and not cfg.runtime.overwrite:
            return
        record = texts_by_id.get(str(doc_id))
        if record is None:
            logger.warning("missing_text_document", qid=qid, document_id=doc_id)
            return
        text_content = str(record.get(cfg.dataset.text_content_field, ""))
        if not text_content and record.get("path"):
            text_content = Path(str(record["path"])).read_text(encoding="utf-8", errors="replace")
        prompt = EXTRACT_RELATION_PROMPT.replace("{Graph_pattern}", graph_pattern).replace("{input_text}", text_content)
        async with semaphore:
            response = await client.generate(prompt)
        write_json(path, {
            "qid": qid,
            "id": str(doc_id),
            "response": response,
            "text_content": text_content,
            "graph_pattern": graph_pattern,
        })
        logger.info("completed_document", qid=qid, document_id=doc_id)

    tasks = []
    for question in questions:
        qid = safe_id(question[cfg.dataset.qid_field])
        pattern_path = cfg.runtime.output_root / "pattern" / f"{qid}.json"
        if not pattern_path.exists():
            raise FileNotFoundError(f"Missing pattern artifact: {pattern_path}")
        pattern = _pattern_text(read_json(pattern_path))
        doc_ids = list(question.get("metadata", {}).get("text_doc_ids", []))
        if cfg.dataset.format == "webqa" and not doc_ids:
            doc_ids = list(question.get("txt_posFacts", []))
        for doc_id in doc_ids:
            tasks.append(extract_doc(question, str(doc_id), pattern))
    await asyncio.gather(*tasks)
