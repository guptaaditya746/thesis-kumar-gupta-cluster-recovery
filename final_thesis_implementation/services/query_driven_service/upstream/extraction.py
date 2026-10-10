import asyncio
import os
import html
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any

import re
import aiohttp

from util.request import text_request

API_URL_base = ""
CONCURRENCY = 8
CACHE_DIR = ""

async def load_question_data(path:str) -> List[Dict]:
    with open(path, "r", encoding='UTF-8') as file:
        return {json.loads(line)['qid']: json.loads(line) for line in file}
async def load_text_data(path:str) -> Dict[str, Dict]:
    with open(path, "r", encoding='UTF-8') as file:
        return {json.loads(line)['id']: json.loads(line) for line in file}


def hash_prompt(prompt: str) -> str:
    return hashlib.md5(prompt.encode()).hexdigest()
def cache_exists(prompt_hash: str) -> bool:
    return os.path.exists(f"{CACHE_DIR}/{prompt_hash}.json")
def validate_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            json.load(file)
        return True
    except json.JSONDecodeError as e:
        return False
    except Exception as e:
        return False
def str_list(str: str) -> List[str]:
    matches = re.search(r'\[([^\]]+)\]', str)
    if matches:
        entity_types_list = matches.group(1).split(", ")
        entity_types_list = [item.strip() for item in entity_types_list]
    else:
        entity_types_list = []
    return entity_types_list
def clean_str(input: Any) -> str:
    if not isinstance(input, str):
        return input
    result = html.unescape(input.strip())
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", result)
async def process_graph_pattern(graph_pattern: str):
    record_delimiter = "##"
    tuple_delimiter = "<|>"
    complete_delimiter = "<|COMPLETE|>"
    records = [r.strip() for r in graph_pattern.split(record_delimiter)]
    entity_list = str_list(records[0])
    edge_type = []
    for record in records[1:]:
        edge_type.append(record.replace(complete_delimiter, ""))
    return {"type_list":entity_list, "edge_list":edge_type}
async def make_request(session: aiohttp.ClientSession, prompt: str, api_base: str,
                       text_content: str, qid: str,graph_pattern: Dict):
    if session is None:
        print("Error: session is None")
        return
    cache_file = f"{CACHE_DIR}/{qid}.json"
    if os.path.exists(cache_file):
        return
    prompt = prompt.replace("{input_text}", text_content)
    result = {}
    result['response'] = text_request(prompt)
    result['qid'] = qid
    result['text_content'] = text_content
    result['graph_pattern'] = graph_pattern
    with open(cache_file, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
async def main():
    questions = json.load(open(r'', "r", encoding="utf-8"))
    questions = {key: item for key, item in questions.items() if item['split'] == "val"}
    k = 1
    async with aiohttp.ClientSession() as session:
        tasks = []
        for key, question in questions.items():
            qid = key
            with open(f"", "r", encoding="utf-8") as file:
                graph_pattern = json.load(file)
            graph_pattern = await process_graph_pattern(graph_pattern['response'])
            new_template = EXTRACT_RELATION_PROMPT.replace("{Graph_pattern}",
                                            "Entity types: [" + ",".join(graph_pattern["type_list"]) + "]\n" + "\n".join(
                                                graph_pattern["edge_list"]))

            text_content = ""
            api_url = API_URL_base
            task = make_request(session, new_template, api_url, text_content, qid, graph_pattern)
            tasks.append(task)
            if len(tasks) == 1:
                await asyncio.gather(*tasks)
                tasks = []

            k += 1
            print(f'{datetime.now()}:{k / len(questions)}')
        if len(tasks) > 0:
            await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())