from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from .clients import TextClient
from .config import ServiceConfig
from .io import safe_id, write_json
from .logging import get_logger
from .prompts import GRAPH_PATTERN_PROMPT


def parse_graph_pattern(text: str) -> dict[str, Any]:
    records = [part.strip() for part in text.split("##") if part.strip()]
    types: list[str] = []
    relationships: list[dict[str, str]] = []
    if records:
        match = re.search(r"\[([^\]]*)\]", records[0])
        if match:
            types = [item.strip().strip('"\'') for item in match.group(1).split(",") if item.strip()]
    for record in records[1:]:
        cleaned = record.replace("<|COMPLETE|>", "").strip().strip("()")
        parts = [p.strip().strip('"') for p in cleaned.split("<|>")]
        if len(parts) >= 4 and parts[0] == "relationship":
            relationships.append({"source_type": parts[1], "target_type": parts[2], "description": parts[3]})
    return {"entity_types": types, "relationships": relationships, "raw": text}


async def run_pattern_stage(cfg: ServiceConfig, questions: list[dict[str, Any]], client: TextClient) -> None:
    logger = get_logger(stage="pattern")
    out_dir = cfg.runtime.output_root / "pattern"
    semaphore = asyncio.Semaphore(cfg.runtime.concurrency)

    async def one(question: dict[str, Any]) -> None:
        qid = safe_id(question[cfg.dataset.qid_field])
        path = out_dir / f"{qid}.json"
        if cfg.runtime.resume and path.exists() and not cfg.runtime.overwrite:
            logger.info("skip_existing", qid=qid)
            return
        prompt = GRAPH_PATTERN_PROMPT.replace("{question}", str(question[cfg.dataset.question_field]))
        async with semaphore:
            response = await client.generate(prompt)
        write_json(path, {"qid": qid, "question": question, "response": response, "pattern": parse_graph_pattern(response)})
        logger.info("completed", qid=qid, output=str(path))

    await asyncio.gather(*(one(q) for q in questions))
