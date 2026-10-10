from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from .clients import EmbeddingClient, ImageSelector, TextClient, VisionClient
from .config import ServiceConfig, dump_resolved_config
from .evaluation import run_evaluation
from .extraction import run_extraction_stage
from .graph import run_construct_stage
from .inference import InferenceEngine
from .io import read_json, read_jsonl, write_json
from .logging import get_logger
from .pattern import run_pattern_stage
from .retrieval import run_retrieval_stage
def _load_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    if path.suffix.lower() == ".json":
        value = read_json(path)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [row for row in value.values() if isinstance(row, dict)]
        raise ValueError(f"Unsupported JSON dataset shape in {path}")
    return read_jsonl(path)

def _load_corpus(root: Path, document_paths: list[str] | None = None) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise ValueError(f"dataset.corpus_root is not a directory: {root}")
    paths = sorted(root.rglob("*.txt")) if document_paths is None else [root / path for path in document_paths]
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix.lower() != ".txt" or not path.is_file():
            continue
        rows.append({"id": path.stem, "path": str(path)})
    return rows


def _index(rows: list[dict[str, Any]], field: str = "id") -> dict[str, dict[str, Any]]:
    return {str(row[field]): row for row in rows if field in row}


def load_inputs(cfg: ServiceConfig) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    questions = _load_rows(cfg.dataset.questions)
    if cfg.dataset.split is not None:
        questions = [q for q in questions if q.get("split") == cfg.dataset.split or q.get("metadata", {}).get("split") == cfg.dataset.split]
    if cfg.runtime.max_questions is not None:
        questions = questions[: cfg.runtime.max_questions]
    if cfg.dataset.format in {"bright", "qa"}:
        # Keep benchmark-only fields out of every runtime stage. The raw question
        # file is reopened only by the dataset-specific evaluator.
        questions = [
            {
                cfg.dataset.qid_field: question[cfg.dataset.qid_field],
                cfg.dataset.question_field: question[cfg.dataset.question_field],
            }
            for question in questions
        ]
        text_rows = []
    elif cfg.dataset.format == "webqa":
        for question in questions:
            metadata = question.setdefault("metadata", {})
            if not metadata.get("text_doc_ids"):
                metadata["text_doc_ids"] = list(question.get("txt_posFacts", []))
        text_rows = _load_corpus(cfg.dataset.corpus_root, [doc_id for question in questions for doc_id in question.get("metadata", {}).get("text_doc_ids", [])]) if cfg.dataset.corpus_root is not None else _load_rows(cfg.dataset.texts)
    else:
        text_rows = _load_rows(cfg.dataset.texts)
    texts = _index(text_rows, cfg.dataset.text_id_field)
    tables = _index(_load_rows(cfg.dataset.tables))
    images = _index(_load_rows(cfg.dataset.images))
    return questions, texts, tables, images


def prepare_run(cfg: ServiceConfig) -> None:
    root = cfg.runtime.output_root
    if root.exists() and cfg.runtime.overwrite and not cfg.runtime.resume:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    dump_resolved_config(cfg, root / "resolved-config.json")
    shutil.copy2(cfg.config_path, root / "service-config.toml")


async def run(cfg: ServiceConfig) -> None:
    logger = get_logger(service="query_driven", operation=cfg.runtime.operation)
    prepare_run(cfg)
    questions, texts, tables, images = load_inputs(cfg)
    logger.info("loaded_inputs", questions=len(questions), texts=len(texts), tables=len(tables), images=len(images))

    text_client = TextClient(cfg.text_model)
    embedding_client = EmbeddingClient(cfg.embedding, cfg.runtime.cache_root)
    vision_client = VisionClient(cfg.vision)
    selector = ImageSelector(cfg.image_selector)

    operation = cfg.runtime.operation
    if operation in {"pipeline", "pattern", "retrieval"}:
        await run_pattern_stage(cfg, questions, text_client)
        if operation == "pattern":
            return
    if operation in {"pipeline", "retrieval"}:
        if cfg.dataset.format in {"bright", "qa"}:
            retrievals = await run_retrieval_stage(cfg, questions, cfg.dataset.corpus_root)
            selected_documents: dict[str, dict[str, Any]] = {}
            for question in questions:
                qid = str(question[cfg.dataset.qid_field])
                result = retrievals.get(qid)
                if result is None:
                    continue
                metadata = question.setdefault("metadata", {})
                metadata["text_doc_ids"] = [item.document_id for item in result.documents]
                for item in result.documents:
                    selected_documents[item.document_id] = {
                        cfg.dataset.text_id_field: item.document_id,
                        cfg.dataset.text_content_field: item.text,
                    }
            texts = _index(list(selected_documents.values()), cfg.dataset.text_id_field)
        if operation == "retrieval":
            return
    if operation in {"pipeline", "extraction"}:
        await run_extraction_stage(cfg, questions, texts, text_client)
        if operation == "extraction":
            return
    if operation in {"pipeline", "construct"}:
        run_construct_stage(cfg, questions, tables, images)
        if operation == "construct":
            return
    if operation in {"pipeline", "inference"}:
        engine = InferenceEngine(cfg, text_client, embedding_client, vision_client, selector)
        semaphore = asyncio.Semaphore(cfg.runtime.concurrency)

        async def one(question: dict[str, Any]):
            async with semaphore:
                return await engine.run_one(question, images)

        results = await asyncio.gather(*(one(q) for q in questions))
        predictions = {str(result["qid"]): result["answer"] for result in results}
        write_json(cfg.runtime.output_root / "predictions.json", predictions)
        if operation == "inference":
            return
    if operation in {"pipeline", "evaluate"} and cfg.evaluation.enabled:
        default_predictions = (
            cfg.runtime.output_root / "retrieved_ids.json"
            if cfg.evaluation.kind == "retrieval"
            else cfg.runtime.output_root / "predictions.json"
        )
        predictions_path = cfg.evaluation.prediction_file or default_predictions
        gold_path = cfg.evaluation.gold_file or cfg.dataset.questions
        if predictions_path is None or gold_path is None:
            raise ValueError("Evaluation requires predictions and gold paths")
        result = run_evaluation(
            predictions_path=predictions_path,
            gold_path=gold_path,
            output_path=cfg.runtime.output_root / "evaluation.json",
            kind=cfg.evaluation.kind,
            gold_field=cfg.evaluation.gold_field,
            prediction_field=cfg.evaluation.prediction_field,
            metrics=cfg.evaluation.metrics,
            selected_qids=[str(question[cfg.dataset.qid_field]) for question in questions],
        )
        logger.info("evaluation_completed", **result["overall"])
