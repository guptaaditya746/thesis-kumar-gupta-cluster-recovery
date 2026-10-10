from __future__ import annotations

import html
import io
import re
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

import networkx as nx

from .config import ServiceConfig
from .io import read_json, safe_id, write_json
from .logging import get_logger

RECORD_DELIMITER = "##"
TUPLE_DELIMITER = "<|>"


def clean_str(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", html.unescape(value.strip()))


def _parts(value: str | None, delimiter: str) -> list[str]:
    return [] if not value else [v for v in value.split(delimiter) if v]


def _merge(existing: str | None, new: str, delimiter: str = "\n") -> str:
    return delimiter.join(sorted(set([*_parts(existing, delimiter), new])))


def extract_entity_by_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    entity = urllib.parse.unquote(path.split("/")[-1]).replace("_", " ")
    return entity or url


def table_to_markdown(table_record: dict[str, Any]) -> str:
    table = table_record["table"]
    header = table["header"]
    lines = ["| " + " | ".join(str(col["column_name"]) for col in header) + " |"]
    lines.append("|" + "---|" * len(header))
    for row in table["table_rows"]:
        lines.append("| " + " | ".join(str(cell.get("text", "")) for cell in row) + " |")
    return "\n".join(lines)


def construct_graph(
    *,
    text_answers: list[dict[str, Any]],
    table: dict[str, Any] | None,
    images: list[dict[str, Any]],
    image_description_dir: Path | None,
    image_title_field: str,
) -> nx.Graph:
    graph = nx.Graph()
    entity_types: dict[str, str] = {}

    for result in text_answers:
        source_doc_id = str(result["id"])
        for record in [r.strip() for r in str(result.get("response", "")).split(RECORD_DELIMITER) if r.strip()]:
            attributes = [clean_str(part).strip('"') for part in re.sub(r"^\(|\)$", "", record).split(TUPLE_DELIMITER)]
            if len(attributes) < 4:
                continue
            kind = attributes[0].strip('"')
            if kind == "entity":
                name, entity_type, description = attributes[1], attributes[2], attributes[3]
                key_name, key_type = name.upper(), entity_type.upper()
                node_id = f"{key_name} Bt: {key_type}"
                entity_types[key_name] = key_type
                if graph.has_node(node_id):
                    graph.nodes[node_id]["description"] = _merge(graph.nodes[node_id].get("description"), description)
                    graph.nodes[node_id]["source_id"] = _merge(graph.nodes[node_id].get("source_id"), source_doc_id, ", ")
                else:
                    graph.add_node(node_id, entity_name=name, type=entity_type, description=description, source_id=source_doc_id)
            elif kind == "relationship":
                source_name, target_name, description = attributes[1], attributes[2], attributes[3]
                source_upper, target_upper = source_name.upper(), target_name.upper()
                source_id = f"{source_upper} Bt: {entity_types.get(source_upper, '')}"
                target_id = f"{target_upper} Bt: {entity_types.get(target_upper, '')}"
                for node_id, name in ((source_id, source_name), (target_id, target_name)):
                    if not graph.has_node(node_id):
                        graph.add_node(node_id, entity_name=name, type="", description="", source_id=source_doc_id)
                if graph.has_edge(source_id, target_id):
                    edge = graph.edges[source_id, target_id]
                    edge["weight"] = float(edge.get("weight", 1.0)) + 1.0
                    edge["description"] = _merge(edge.get("description"), description)
                    edge["source_id"] = _merge(edge.get("source_id"), source_doc_id, ", ")
                else:
                    graph.add_edge(source_id, target_id, weight=1.0, description=description, source_id=source_doc_id)

    if table is not None:
        title = str(table.get("title", table.get("id", "table")))
        title_upper = title.upper()
        anchor = f"{title_upper} Bt: {entity_types.get(title_upper, '')}"
        if not graph.has_node(anchor):
            graph.add_node(anchor, entity_name=title, type="", description="", source_id=str(table.get("id", "")))
        table_name = str(table.get("table", {}).get("table_name", "table"))
        table_node = f"{title_upper} {table_name.upper()} Bt: TABLE"
        graph.add_node(table_node, entity_name=f"{title} {table_name}", type="TABLE", description=table_to_markdown(table), source_id=str(table.get("id", "")))
        graph.add_edge(anchor, table_node, weight=1.0, description=f"{title} {table_name} table", source_id=str(table.get("id", "")))

    for image in sorted(images, key=lambda row: str(row.get("id", ""))):
        image_id = str(image.get("id", ""))
        description = str(image.get("description", ""))
        if image_description_dir is not None:
            candidate = image_description_dir / f"{image_id}.txt"
            if candidate.exists():
                description = candidate.read_text(encoding="utf-8")
        if not description:
            continue
        title = str(image.get(image_title_field, image_id))
        entity_name = extract_entity_by_url(title)
        entity_upper = entity_name.upper()
        anchor = f"{entity_upper} Bt: {entity_types.get(entity_upper, '')}"
        if not graph.has_node(anchor):
            graph.add_node(anchor, entity_name=entity_name, type="", description="", source_id=image_id)
        image_node = f"{entity_upper} Bt: IMAGE"
        graph.add_node(image_node, entity_name=entity_name, type="IMAGE", description=description, source_id=image_id)
        graph.add_edge(anchor, image_node, weight=1.0, description=f"{entity_name}'s picture", source_id=image_id)
    return graph


def graph_to_string(graph: nx.Graph) -> str:
    blocks: list[str] = []
    for label, expected in (("TEXT", None), ("IMAGE", "IMAGE"), ("TABLE", "TABLE")):
        blocks.append(f"======= BEGIN: {label} NODES BLOCK =======")
        for node_id, data in sorted(graph.nodes(data=True), key=lambda item: item[0]):
            node_type = str(data.get("type", ""))
            if expected is None and node_type in {"IMAGE", "TABLE"}:
                continue
            if expected is not None and node_type != expected:
                continue
            blocks.extend([f"Name: {data.get('entity_name', '')}", f"Type: {node_type or 'unspecified'}", f"Description: {data.get('description', '')}", "---"])
        blocks.append(f"======= END: {label} NODES BLOCK =======")
        blocks.append("")
    blocks.append("======= BEGIN: RELATIONSHIPS BLOCK =======")
    for left, right, data in sorted(graph.edges(data=True), key=lambda item: (item[0], item[1])):
        blocks.extend([
            f"Node 1 Name: {graph.nodes[left].get('entity_name', '')}",
            f"Node 2 Name: {graph.nodes[right].get('entity_name', '')}",
            f"Relationship between Node 1 and Node 2: {data.get('description', '')}",
            "----------",
        ])
    blocks.append("======= END: RELATIONSHIPS BLOCK =======")
    return "\n".join(blocks)


def graph_to_graphml_str(graph: nx.Graph) -> str:
    with io.BytesIO() as output:
        nx.write_graphml(graph, output)
        return output.getvalue().decode("utf-8")


def run_construct_stage(
    cfg: ServiceConfig,
    questions: list[dict[str, Any]],
    tables_by_id: dict[str, dict[str, Any]],
    images_by_id: dict[str, dict[str, Any]],
) -> None:
    logger = get_logger(stage="construct")
    out_dir = cfg.runtime.output_root / "graph"
    out_dir.mkdir(parents=True, exist_ok=True)
    for question in questions:
        qid = safe_id(question[cfg.dataset.qid_field])
        graph_path = out_dir / f"{qid}.graphml"
        if cfg.runtime.resume and graph_path.exists() and not cfg.runtime.overwrite:
            logger.info("skip_existing", qid=qid)
            continue
        metadata = question.get("metadata", {})
        text_answers = []
        for doc_id in metadata.get("text_doc_ids", []):
            path = cfg.runtime.output_root / "extraction" / qid / f"{safe_id(doc_id)}.json"
            if path.exists():
                text_answers.append(read_json(path))
        table = tables_by_id.get(str(metadata.get("table_id")))
        images = [images_by_id[str(image_id)] for image_id in metadata.get("image_doc_ids", []) if str(image_id) in images_by_id]
        graph = construct_graph(
            text_answers=text_answers,
            table=table,
            images=images,
            image_description_dir=cfg.dataset.image_description_dir,
            image_title_field=cfg.dataset.image_title_field,
        )
        nx.write_graphml(graph, graph_path)
        write_json(out_dir / f"{qid}.summary.json", {"qid": qid, "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges()})
        logger.info("completed", qid=qid, nodes=graph.number_of_nodes(), edges=graph.number_of_edges())
