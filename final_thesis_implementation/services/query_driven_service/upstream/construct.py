import io
import numbers
import os
import hashlib
import json
from typing import List, Dict, Any, Mapping
import html
import re
import networkx as nx
import pandas as pd
import urllib.parse

record_delimiter = "##"
tuple_delimiter = "<|>"
join_descriptions_flag = True
def clean_str(input: Any) -> str:
    if not isinstance(input, str):
        return input

    result = html.unescape(input.strip())
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", result)
def _unpack_descriptions(data: Mapping) -> list[str]:
    value = data.get("description", None)
    return [] if value is None else value.split("\n")
def _unpack_source_ids(data: Mapping) -> list[str]:
    value = data.get("source_id", None)
    return [] if value is None else value.split(", ")
def load_jsonl_data(path):
    with open(path, "r", encoding='UTF-8') as file:
        return [json.loads(line) for line in file]
def extract_entity_by_wikiurl(url):
    path = urllib.parse.urlparse(url).path
    entity = path.split('/')[-1]
    entity = urllib.parse.unquote(entity)
    entity = entity.replace('_', ' ')
    return entity
def table_to_markdown(table):
    markdown = ""
    table = table['table']
    header = table['header']
    markdown += "| " + " | ".join(col['column_name'] for col in header) + " |\n"
    markdown += "|" + "---|" * len(header) + "\n"
    for row in table['table_rows']:
        markdown += "| " + " | ".join(cell['text'] for cell in row) + " |\n"
    return markdown.strip()

def construct_graph(text_answers, table, question, texts, images):
    graph = nx.Graph()
    # text_wikitoid = {text['url']: text['id'] for text in texts if text['id'] in question['metadata']['text_doc_ids']}
    # image_wikitoid = {image['url']: image['id'] for image in images if image['id'] in question['metadata']['image_doc_ids']}

    entity_dict = {}
    for result in text_answers:
        source_doc_id = result['id']
        extracted_data = result['response']
        records = [r.strip() for r in extracted_data.split(record_delimiter)]

        for record in records:
            record = re.sub(r"^\(|\)$", "", record.strip())
            record_attributes = record.split(tuple_delimiter)

            if record_attributes[0] == '"entity"' and len(record_attributes) >= 4:
                # add this record as a node in the G
                entity_name = clean_str(record_attributes[1]).strip('"')
                entity_type = clean_str(record_attributes[2]).strip('"')
                entity_description = clean_str(record_attributes[3]).strip('"')
                entity_type_upper = entity_type.upper()
                entity_name_upper = entity_name.upper()
                entity_uuid = entity_name_upper + " Bt: " + entity_type_upper
                if entity_uuid in graph.nodes():
                    node = graph.nodes[entity_uuid]
                    node["description"] = "\n".join(
                        list({
                            *_unpack_descriptions(node),
                            entity_description,
                        })
                    )
                    node["source_id"] = ", ".join(
                        list({
                            *_unpack_source_ids(node),
                            str(source_doc_id),
                        })
                    )
                else:
                    entity_dict[entity_name_upper] = entity_type_upper
                    graph.add_node(
                        entity_uuid,
                        entity_name=entity_name,
                        type=entity_type,
                        description=entity_description,
                        source_id=str(source_doc_id),
                    )

            if (
                    record_attributes[0] == '"relationship"'
                    and len(record_attributes) >= 4
            ):
                source_entity_name = clean_str(record_attributes[1]).strip('"')
                source_entity_name_upper = source_entity_name.upper()
                target_entity_name = clean_str(record_attributes[2]).strip('"')
                target_entity_name_upper = target_entity_name.upper()
                edge_description = clean_str(record_attributes[3]).strip('"')
                edge_source_id = clean_str(str(source_doc_id))
                weight = 1.0
                if source_entity_name_upper not in entity_dict:
                    entity_dict[source_entity_name_upper] = ""
                    source_entity_uuid = source_entity_name_upper + " Bt: "
                    if source_entity_uuid not in graph.nodes():
                        graph.add_node(
                            source_entity_uuid,
                            entity_name=source_entity_name,
                            type="",
                            description="",
                            source_id=edge_source_id,
                        )
                else:
                    source_entity_uuid = source_entity_name_upper + " Bt: " + entity_dict[source_entity_name_upper]
                if target_entity_name_upper not in entity_dict:
                    entity_dict[target_entity_name_upper] = ""
                    target_entity_uuid = target_entity_name_upper + " Bt: "
                    graph.add_node(
                        target_entity_uuid,
                        entity_name=target_entity_name,
                        type="",
                        description="",
                        source_id=edge_source_id,
                    )
                else:
                    target_entity_uuid = target_entity_name_upper + " Bt: " + entity_dict[target_entity_name_upper]

                if graph.has_edge(source_entity_uuid, target_entity_uuid):
                    edge_data = graph.get_edge_data(source_entity_uuid, target_entity_uuid)
                    if edge_data is not None:
                        weight += edge_data["weight"]
                        if join_descriptions_flag:
                            edge_description = "\n".join(
                                list({
                                    *_unpack_descriptions(edge_data),
                                    edge_description,
                                })
                            )
                        edge_source_id = ", ".join(
                            list({
                                *_unpack_source_ids(edge_data),
                                str(source_doc_id),
                            })
                        )
                graph.add_edge(
                    source_entity_uuid,
                    target_entity_uuid,
                    weight=weight,
                    description=edge_description,
                    source_id=edge_source_id,
                )
    markdown_table = table_to_markdown(table)
    table_title = table['title']
    table_title_upper = table_title.upper()
    if table_title_upper not in entity_dict:
        entity_dict[table_title_upper] = ""
        graph.add_node(
            table_title_upper + " Bt: ",
            entity_name=table_title,
            type="",
            description="",
            source_id=table['id'],
        )
        graph.add_node(
            table_title_upper + " " + table['table']['table_name'].upper() + " Bt: TABLE",
            entity_name=table['title'] + " " + table['table']['table_name'],
            type="TABLE",
            description=markdown_table,
            source_id=table['id'],
        )
        graph.add_edge(
            table_title_upper + " Bt: ",
            table_title_upper + " " + table['table']['table_name'].upper() + " Bt: TABLE",
            entity_name=table['title'] + " " + table['table']['table_name'],
            weight=1,
            description=table['title'] + " " + table['table']['table_name'] + " table",
            source_id=table['id']
        )
    else:
        graph.add_node(
            table_title_upper + " " + table['table']['table_name'].upper() + " Bt: TABLE",
            entity_name=table['title'] + " " + table['table']['table_name'],
            type="TABLE",
            description=markdown_table,
            source_id=table['id'],
        )
        graph.add_edge(
            table_title_upper + " Bt: " + entity_dict[table_title_upper],
            table_title_upper + " " + table['table']['table_name'].upper() + " Bt: TABLE",
            entity_name=table['title'] + " " + table['table']['table_name'],
            weight=1,
            description=table['title'] + " " + table['table']['table_name'] + " table",
            source_id=table['id']
        )
    # 以同样的方式将图片信息连接上
    for image in images:
        try:
            with open(r"/home/changguojie/MMRAG/MMQA/image_description//"+ image['id'] + ".txt", "r", encoding='UTF-8') as file:
                image_description = file.read()
        except FileNotFoundError:
            continue
        image_entity_name = extract_entity_by_wikiurl(image['title'])
        image_entity_name_upper = image_entity_name.upper()
        if image_entity_name_upper not in entity_dict:
            entity_dict[image_entity_name_upper] = ""
            graph.add_node(
                image_entity_name_upper + " Bt: ",
                entity_name=image_entity_name,
                type="",
                description="",
                source_id=image['id']
            )
            graph.add_node(
                image_entity_name_upper + " Bt: IMAGE",
                entity_name=image_entity_name if image['title'] == image_entity_name else f"{image_entity_name} {image['title']}",
                type="IMAGE",
                description=image_description,
                source_id=image['id']
            )
            graph.add_edge(
                image_entity_name_upper + " Bt: ",
                image_entity_name_upper + " Bt: IMAGE",
                weight=1,
                description=image['title'] + " 's picture",
            )
        else:
            graph.add_node(
                image_entity_name_upper + " Bt: IMAGE",
                entity_name=image_entity_name if image['title'] == image_entity_name else f"{image_entity_name} {image['title']}",
                type="IMAGE",
                description=image_description,
                source_id=image['id']
            )
            graph.add_edge(
                image_entity_name_upper + " Bt: " + entity_dict[image_entity_name_upper],
                image_entity_name_upper + " Bt: IMAGE",
                weight=1,
                description=image_entity_name + " 's picture",
            )
    return graph

def graph_to_graphml_str(graph):
    with io.BytesIO() as byte_output:
        nx.write_graphml(graph, byte_output)
        byte_output.seek(0)
        graphml_str = byte_output.read().decode('utf-8')
    return graphml_str


def main():
    question_file = ""
    table_file = ""
    image_file = ""
    text_file = ""
    answer_text_cache =
    questiones = load_jsonl_data(question_file)
    tables = load_jsonl_data(table_file)
    tables = {table['id']: table for table in tables}
    images = load_jsonl_data(image_file)
    images = {image['id']: image for image in images}
    texts = load_jsonl_data(text_file)
    texts = {text['id']: text for text in texts}
    for question in questiones:
        text_doc_ids = question['metadata']['text_doc_ids']
        image_doc_ids = question['metadata']['image_doc_ids']
        table_id = question['metadata']['table_id']
        text_results = []
        for text_doc_id in text_doc_ids:
            with open(os.path.join(answer_text_cache, f"{question['qid']}_{text_doc_id}.json"), "r", encoding='UTF-8') as file:
                text_results.append(json.load(file))
        table = tables[table_id]
        q_graph = construct_graph(text_results, table, question, texts, [images[image_id] for image_id in image_doc_ids])
        print(f"Graph has {q_graph.number_of_nodes()} nodes and {q_graph.number_of_edges()} edges")
        nx.write_graphml(q_graph, f"")