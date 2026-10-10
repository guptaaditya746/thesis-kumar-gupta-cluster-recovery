from __future__ import annotations

import json
import re
import string
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
try:
    from word2number.w2n import word_to_num
except ModuleNotFoundError:  # pragma: no cover - uv sync installs dependency
    def word_to_num(text: str):
        raise ValueError(text)

from .io import read_jsonl, write_json

MULTI_HOP_QUESTION_TYPES = {
    "Compose(TextQ,ImageListQ)",
    "Compose(ImageQ,TextQ)",
    "Intersect(ImageListQ,TextQ)",
}
EXCLUDE = set(string.punctuation)


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def _normalize_number(text: str) -> str:
    if _is_number(text):
        return str(float(text))
    try:
        return str(float(word_to_num(text)))
    except ValueError:
        return text


def normalize_answer(text: str) -> str:
    tokens = re.split(r" |\-", str(text).lower())
    result = []
    for token in tokens:
        if not _is_number(token):
            token = "".join(ch for ch in token if ch not in EXCLUDE)
        token = re.sub(r"\b(a|an|the)\b", " ", token)
        token = _normalize_number(" ".join(token.split()))
        if token.strip():
            result.append(token.strip())
    return " ".join(result)


def _answer_bags(answer: str | list[str]) -> tuple[list[str], list[set[str]]]:
    spans = answer if isinstance(answer, list) else [answer]
    normalized = [normalize_answer(str(span)) for span in spans]
    return normalized, [set(span.split()) for span in normalized]


def _f1(predicted: set[str], gold: set[str]) -> float:
    common = len(predicted & gold)
    precision = common / len(predicted) if predicted else 1.0
    recall = common / len(gold) if gold else 1.0
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _numbers_compatible(gold: set[str], predicted: set[str]) -> bool:
    gold_numbers = {x for x in gold if _is_number(x)}
    predicted_numbers = {x for x in predicted if _is_number(x)}
    return not gold_numbers or bool(gold_numbers & predicted_numbers)


def list_f1(predicted: str | list[str], gold: str | list[str]) -> float:
    _, pred_bags = _answer_bags(predicted)
    _, gold_bags = _answer_bags(gold)
    scores = np.zeros((len(gold_bags), len(pred_bags)))
    for gi, g in enumerate(gold_bags):
        for pi, p in enumerate(pred_bags):
            if _numbers_compatible(g, p):
                scores[gi, pi] = _f1(p, g)
    row, col = linear_sum_assignment(-scores)
    aligned = np.zeros(max(len(gold_bags), len(pred_bags)))
    for r, c in zip(row, col):
        aligned[r] = scores[r, c]
    return float(np.mean(aligned)) if len(aligned) else 0.0


def list_em(predicted: str | list[str], gold: str | list[str]) -> float:
    pred_norm, _ = _answer_bags(predicted)
    gold_norm, _ = _answer_bags(gold)
    return 1.0 if set(pred_norm) == set(gold_norm) and len(pred_norm) == len(gold_norm) else 0.0


def _prediction_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("answer", "")
    text = str(value)
    tag = re.search(r"<\|Answer\|>([\s\S]*?)<\|\\Answer\|>", text)
    return tag.group(1).strip() if tag else text.strip()


def evaluate(predictions: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
    per_item: dict[str, dict[str, float]] = {}
    by_modality: dict[str, list[dict[str, float]]] = {}
    by_hop: dict[str, list[dict[str, float]]] = {}
    by_type: dict[str, list[dict[str, float]]] = {}

    for example in examples:
        qid = str(example.get("qid", example.get("id", example.get("query_id", ""))))
        gold = [str(item["answer"]) for item in example.get("answers", [])] if example.get("answers") else [str(example.get("answer", ""))]
        prediction = _prediction_text(predictions.get(qid, ""))
        pred_value: str | list[str] = prediction
        if len(gold) > 1:
            pred_value = [part.strip() for part in re.split(r"\s*[,，]\s*", prediction) if part.strip()]
        scores = {"list_em": list_em(pred_value, gold), "list_f1": list_f1(pred_value, gold)}
        per_item[qid] = scores
        modality = next(iter({str(item.get("modality", "unknown")) for item in example.get("answers", [])}), "unknown")
        qtype = str(example.get("metadata", {}).get("type", "unknown"))
        hop = "Multi-hop" if qtype in MULTI_HOP_QUESTION_TYPES else "Single-hop"
        by_modality.setdefault(modality, []).append(scores)
        by_hop.setdefault(hop, []).append(scores)
        by_type.setdefault(qtype, []).append(scores)

    def summarize(groups: dict[str, list[dict[str, float]]]) -> dict[str, Any]:
        return {
            name: {
                "count": len(rows),
                "list_em": 100.0 * float(np.mean([r["list_em"] for r in rows])) if rows else 0.0,
                "list_f1": 100.0 * float(np.mean([r["list_f1"] for r in rows])) if rows else 0.0,
            }
            for name, rows in sorted(groups.items())
        }

    rows = list(per_item.values())
    return {
        "overall": {
            "count": len(rows),
            "list_em": 100.0 * float(np.mean([r["list_em"] for r in rows])) if rows else 0.0,
            "list_f1": 100.0 * float(np.mean([r["list_f1"] for r in rows])) if rows else 0.0,
        },
        "by_modality": summarize(by_modality),
        "by_hop": summarize(by_hop),
        "by_question_type": summarize(by_type),
        "per_item": per_item,
    }



def _retrieval_scores(retrieved: list[str], gold: list[str], k: int) -> dict[str, float]:
    ranked = retrieved[:k]
    gold_set = set(gold)
    hits = [index for index, doc_id in enumerate(ranked) if doc_id in gold_set]
    recall = len(set(ranked) & gold_set) / len(gold_set) if gold_set else 0.0
    dcg = sum(1.0 / np.log2(index + 2) for index in hits)
    ideal_hits = min(k, len(gold_set))
    idcg = sum(1.0 / np.log2(index + 2) for index in range(ideal_hits))
    ndcg = dcg / idcg if idcg else 0.0
    mrr = 1.0 / (hits[0] + 1) if hits else 0.0
    return {"ndcg": float(ndcg), "recall": float(recall), "mrr": float(mrr)}


def evaluate_retrieval(
    predictions: dict[str, Any],
    examples: list[dict[str, Any]],
    *,
    gold_field: str = "gold_ids",
    prediction_field: str = "retrieved_ids",
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    requested = metrics or ["ndcg@10", "recall@10", "recall@20", "mrr"]
    per_item: dict[str, dict[str, float]] = {}
    for example in examples:
        qid = str(example.get("id", example.get("qid", example.get("query_id", ""))))
        gold = [str(value) for value in example.get(gold_field, [])]
        raw = predictions.get(qid, [])
        retrieved = raw.get(prediction_field, []) if isinstance(raw, dict) else raw
        retrieved = [str(value) for value in retrieved]
        scores: dict[str, float] = {}
        for metric in requested:
            if metric.startswith("ndcg@"):
                k = int(metric.split("@", 1)[1])
                scores[metric] = _retrieval_scores(retrieved, gold, k)["ndcg"]
            elif metric.startswith("recall@"):
                k = int(metric.split("@", 1)[1])
                scores[metric] = _retrieval_scores(retrieved, gold, k)["recall"]
            elif metric == "mrr":
                scores[metric] = _retrieval_scores(retrieved, gold, max(len(retrieved), 1))["mrr"]
        per_item[qid] = scores
    overall = {
        "count": len(per_item),
        **{
            metric: float(np.mean([scores.get(metric, 0.0) for scores in per_item.values()]))
            if per_item else 0.0
            for metric in requested
        },
    }
    return {"overall": overall, "per_item": per_item}


def _qa_gold_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return [""]
    return [str(value)]


def _token_f1_text(predicted: str, gold: str) -> float:
    predicted_tokens = normalize_answer(predicted).split()
    gold_tokens = normalize_answer(gold).split()
    if not predicted_tokens and not gold_tokens:
        return 1.0
    if not predicted_tokens or not gold_tokens:
        return 0.0
    predicted_counts = Counter(predicted_tokens)
    gold_counts = Counter(gold_tokens)
    common = sum((predicted_counts & gold_counts).values())
    if common == 0:
        return 0.0
    precision = common / len(predicted_tokens)
    recall = common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def evaluate_answer_qa(
    predictions: dict[str, Any],
    examples: list[dict[str, Any]],
    *,
    gold_field: str = "answer",
    prediction_field: str = "answer",
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    requested = metrics or ["exact_match", "token_f1"]
    per_item: dict[str, dict[str, float]] = {}
    for example in examples:
        qid = str(example.get("id", example.get("qid", example.get("query_id", ""))))
        gold_values = _qa_gold_values(example.get(gold_field, ""))
        raw_prediction = predictions.get(qid, "")
        if isinstance(raw_prediction, dict):
            raw_prediction = raw_prediction.get(prediction_field, raw_prediction.get("answer", ""))
        prediction = _prediction_text(raw_prediction)
        scores: dict[str, float] = {}
        if "exact_match" in requested:
            scores["exact_match"] = max(
                (1.0 if normalize_answer(prediction) == normalize_answer(gold) else 0.0)
                for gold in gold_values
            )
        if "token_f1" in requested:
            scores["token_f1"] = max((_token_f1_text(prediction, gold) for gold in gold_values), default=0.0)
        per_item[qid] = scores
    overall = {
        "count": len(per_item),
        **{
            metric: 100.0 * float(np.mean([scores.get(metric, 0.0) for scores in per_item.values()]))
            if per_item else 0.0
            for metric in requested
        },
    }
    return {"overall": overall, "per_item": per_item}


def run_evaluation(
    *,
    predictions_path: Path,
    gold_path: Path,
    output_path: Path,
    kind: str = "mmqa_answer",
    gold_field: str = "gold_ids",
    prediction_field: str = "retrieved_ids",
    metrics: list[str] | None = None,
    selected_qids: list[str] | None = None,
) -> dict[str, Any]:
    predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
    examples = read_jsonl(gold_path)
    if selected_qids is not None:
        selected = set(selected_qids)
        examples = [
            example
            for example in examples
            if str(example.get("id", example.get("qid", example.get("query_id", ""))))
            in selected
        ]
        found = {
            str(example.get("id", example.get("qid", example.get("query_id", ""))))
            for example in examples
        }
        missing = selected - found
        if missing:
            raise ValueError(f"Selected question IDs missing from gold data: {sorted(missing)}")
    if kind == "retrieval":
        result = evaluate_retrieval(
            predictions,
            examples,
            gold_field=gold_field,
            prediction_field=prediction_field,
            metrics=metrics,
        )
    elif kind == "answer_qa":
        result = evaluate_answer_qa(
            predictions,
            examples,
            gold_field=gold_field,
            prediction_field=prediction_field,
            metrics=metrics,
        )
    elif kind == "mmqa_answer":
        result = evaluate(predictions, examples)
    else:
        raise ValueError(f"Unsupported evaluation kind: {kind}")
    write_json(output_path, result)
    return result
