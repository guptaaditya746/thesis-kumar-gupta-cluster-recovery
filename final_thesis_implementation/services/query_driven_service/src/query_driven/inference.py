from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from .clients import EmbeddingClient, ImageSelector, TextClient, VisionClient
from .config import ServiceConfig
from .graph import graph_to_graphml_str, graph_to_string
from .io import safe_id, write_json
from .logging import get_logger
from .prompts import (
    DETERMINE_ANSWER_PROMPT,
    GET_FINAL_ANSWER_PROMPT,
    HEAD_NODE_PROMPT,
    IMAGE_FEATURE_PROMPT,
    IMAGE_QA_PROMPT,
    IMAGEQ_PROMPT,
    LLM_ANSWER_PROMPT,
    SELECT_IMAGE_PROMPT,
    TABLE_QA_PROMPT,
)

ANSWER_LIST_RE = re.compile(r"<\|Answer\|>([\s\S]*?)<\|\\Answer\|>")


def extract_answer_list(text: str) -> list[Any]:
    match = ANSWER_LIST_RE.search(text or "")
    if not match:
        return []
    try:
        value = json.loads(match.group(1).strip())
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    av, bv = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return 0.0 if denom == 0.0 else float(np.dot(av, bv) / denom)


async def _nearest_nodes(
    graph: nx.Graph,
    queries: list[str],
    embedding: EmbeddingClient,
    top_k: int,
    *,
    use_description: bool,
) -> list[str]:
    if not queries or graph.number_of_nodes() == 0:
        return []
    node_items = sorted(graph.nodes(data=True), key=lambda item: item[0])
    node_texts = [str(data.get("description" if use_description else "entity_name", "")) or str(node_id) for node_id, data in node_items]
    node_vectors = await asyncio.gather(*(embedding.embed(text) for text in node_texts))
    query_vectors = await asyncio.gather(*(embedding.embed(query) for query in queries))
    scores: dict[str, float] = {str(node_id): -1.0 for node_id, _ in node_items}
    for qv in query_vectors:
        for (node_id, _), nv in zip(node_items, node_vectors):
            scores[str(node_id)] = max(scores[str(node_id)], _cosine(qv, nv))
    return [node for node, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]]


class ClipRanker:
    def __init__(self, cfg: ServiceConfig) -> None:
        self.cfg = cfg
        self._model = None
        self._processor = None

    def rank(self, image_paths: list[Path], text: str) -> list[int]:
        if not self.cfg.clip.enabled:
            return list(range(min(self.cfg.clip.top_k, len(image_paths))))
        try:
            import torch
            from PIL import Image
            from transformers import AutoModel, AutoProcessor
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install the 'multimodal' extra to enable CLIP ranking") from exc
        if self._model is None:
            self._model = AutoModel.from_pretrained(self.cfg.clip.model, device_map=self.cfg.clip.device_map)
            self._processor = AutoProcessor.from_pretrained(self.cfg.clip.model)
        images = [Image.open(path).convert("RGB") for path in image_paths]
        inputs = self._processor(text=[text], images=images, max_length=16, padding="max_length", truncation=True, return_tensors="pt")
        with torch.no_grad():
            outputs = self._model(**inputs)
        k = min(self.cfg.clip.top_k, len(image_paths))
        return torch.topk(outputs.logits_per_text, k=k, dim=1)[1].tolist()[0]


class InferenceEngine:
    def __init__(self, cfg: ServiceConfig, text: TextClient, embedding: EmbeddingClient, vision: VisionClient, selector: ImageSelector) -> None:
        self.cfg = cfg
        self.text = text
        self.embedding = embedding
        self.vision = vision
        self.selector = selector
        self.clip = ClipRanker(cfg)
        self.logger = get_logger(stage="inference")

    def _image_path(self, image_record: dict[str, Any]) -> Path | None:
        if self.cfg.dataset.image_root is None:
            return None
        rel = image_record.get(self.cfg.dataset.image_path_field)
        return None if rel is None else (self.cfg.dataset.image_root / str(rel)).resolve()

    async def _image_seed_nodes(self, question_text: str, graph: nx.Graph, images_by_id: dict[str, dict[str, Any]]) -> list[str]:
        prompt = IMAGE_FEATURE_PROMPT.replace("{question}", question_text)
        descriptions = extract_answer_list(await self.text.generate(prompt))
        if not descriptions:
            return []
        image_nodes: list[str] = []
        image_paths: list[Path] = []
        for node_id, data in sorted(graph.nodes(data=True), key=lambda item: item[0]):
            if data.get("type") != "IMAGE":
                continue
            record = images_by_id.get(str(data.get("source_id")))
            path = self._image_path(record or {})
            if path and path.exists():
                image_nodes.append(str(node_id))
                image_paths.append(path)
        if not image_paths:
            return []
        selected: list[str] = []
        for description in descriptions:
            ranking = self.clip.rank(image_paths, str(description))
            candidates = [image_paths[i] for i in ranking]
            if not candidates:
                continue
            prompt = SELECT_IMAGE_PROMPT.replace("{description}", str(description))
            local_index = await self.selector.select(prompt, candidates[:3])
            chosen_global_index = ranking[min(local_index, len(ranking) - 1)]
            node_id = image_nodes[chosen_global_index]
            selected.append(node_id)
            graph.nodes[node_id]["description"] = f'This image matches the description in the question "{description}"'
        return selected

    async def run_one(self, question: dict[str, Any], images_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
        qid_raw = str(question[self.cfg.dataset.qid_field])
        qid = safe_id(qid_raw)
        output = self.cfg.runtime.output_root / "inference" / f"{qid}.json"
        if self.cfg.runtime.resume and output.exists() and not self.cfg.runtime.overwrite:
            return json.loads(output.read_text(encoding="utf-8"))
        graph_path = self.cfg.runtime.output_root / "graph" / f"{qid}.graphml"
        if not graph_path.exists():
            raise FileNotFoundError(f"Missing graph artifact: {graph_path}")
        graph = nx.read_graphml(graph_path)
        question_text = str(question[self.cfg.dataset.question_field])

        question_seeds = await _nearest_nodes(graph, [question_text], self.embedding, self.cfg.runtime.initial_entity_count, use_description=True)
        head_response = await self.text.generate(HEAD_NODE_PROMPT.replace("{question}", question_text))
        head_terms = [str(item) for item in extract_answer_list(head_response)] or [question_text]
        head_seeds = await _nearest_nodes(graph, head_terms, self.embedding, self.cfg.runtime.initial_entity_count, use_description=False)
        image_seeds = await self._image_seed_nodes(question_text, graph, images_by_id)
        seed_nodes = sorted(set(question_seeds + head_seeds + image_seeds))

        essential = nx.Graph()
        for node_id in seed_nodes:
            if graph.has_node(node_id):
                essential.add_node(node_id, **graph.nodes[node_id])

        calls = {"iterations": 0, "image_questions": 0, "table_queries": 0, "image_seeds": len(image_seeds)}
        sufficiency_response = ""
        answered = False
        for iteration in range(self.cfg.runtime.max_refinement_iterations):
            calls["iterations"] = iteration
            sufficiency_prompt = DETERMINE_ANSWER_PROMPT.replace("{question}", question_text).replace("{GraphML}", graph_to_string(essential))
            sufficiency_response = await self.text.generate(sufficiency_prompt)
            match = re.search(r"Answer:\s*(Yes|No)", sufficiency_response, re.IGNORECASE)
            if match and match.group(1).lower() == "yes":
                answered = True
                break

            image_query = await self.text.generate(IMAGEQ_PROMPT.replace("{question}", question_text).replace("{GraphML}", graph_to_string(essential)))
            for item in extract_answer_list(image_query):
                if not isinstance(item, dict):
                    continue
                for image_name, image_question in item.items():
                    for node_id, data in list(essential.nodes(data=True)):
                        if data.get("type") != "IMAGE" or str(data.get("entity_name", "")).strip('"') != str(image_name).strip('"'):
                            continue
                        record = images_by_id.get(str(data.get("source_id")))
                        path = self._image_path(record or {})
                        if path and path.exists() and self.vision.config.enabled:
                            prompt = IMAGE_QA_PROMPT.replace("{question}", str(image_question)).replace("{title}", str(data.get("entity_name", "")))
                            answer = await self.vision.answer(prompt=prompt, image_path=path)
                            if answer:
                                essential.nodes[node_id]["description"] = str(data.get("description", "")) + f"\n{image_question}\nAnswer: {answer}"
                                calls["image_questions"] += 1

            for node_id in list(essential.nodes):
                if not graph.has_node(node_id):
                    continue
                for neighbor in sorted(graph.neighbors(node_id)):
                    if not essential.has_node(neighbor):
                        essential.add_node(neighbor, **graph.nodes[neighbor])
                    if not essential.has_edge(node_id, neighbor):
                        essential.add_edge(node_id, neighbor, **graph.edges[node_id, neighbor])

            table_nodes = [(node_id, data) for node_id, data in essential.nodes(data=True) if data.get("type") == "TABLE"]
            if table_nodes:
                node_id, data = sorted(table_nodes, key=lambda item: item[0])[0]
                table_prompt = TABLE_QA_PROMPT.replace("{Question}", question_text).replace("{Table name}", str(data.get("entity_name", ""))).replace("{Table content}", str(data.get("description", "")))
                candidates = [str(item) for item in extract_answer_list(await self.text.generate(table_prompt))]
                calls["table_queries"] += 1
                extra_nodes = await _nearest_nodes(graph, candidates, self.embedding, self.cfg.runtime.table_entity_count, use_description=False) if candidates else []
                for extra in extra_nodes:
                    if not essential.has_node(extra):
                        essential.add_node(extra, **graph.nodes[extra])

        if answered:
            reasoning = re.sub(r"^\s*Answer:\s*(Yes|No)\s*$", "", sufficiency_response, flags=re.IGNORECASE | re.MULTILINE).strip()
            final_prompt = GET_FINAL_ANSWER_PROMPT.replace("{question}", question_text).replace("{my_answer}", reasoning)
        else:
            final_prompt = LLM_ANSWER_PROMPT.replace("{question}", question_text).replace("{GraphML}", graph_to_string(essential))
        final_answer = await self.text.generate(final_prompt)
        result = {
            "qid": qid_raw,
            "artifact_id": qid,
            "answer": final_answer,
            "answered_before_limit": answered,
            "calls": calls,
            "seed_nodes": seed_nodes,
            "graph": graph_to_graphml_str(essential),
        }
        write_json(output, result)
        self.logger.info("completed", qid=qid, answered_before_limit=answered, nodes=essential.number_of_nodes())
        return result
