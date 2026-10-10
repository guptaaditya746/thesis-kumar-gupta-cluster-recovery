import asyncio
import os
from datetime import datetime

import aiohttp
import hashlib
import json
from typing import List, Dict
from prompt.prompt import *
import math
import networkx as nx

API_URL = ""
API_URL_base = ""
CONCURRENCY = 16
JSON_FILE_PATH = ""
CACHE_DIR = ""

async def load_json_data() -> List[Dict]:
    if "WebQA" in JSON_FILE_PATH:
        with open(JSON_FILE_PATH, "r", encoding='UTF-8') as file:
            return json.load(file)
    with open(JSON_FILE_PATH, "r", encoding='UTF-8') as file:
        return [json.loads(line) for line in file]


def hash_prompt(prompt: str) -> str:
    return hashlib.md5(prompt.encode()).hexdigest()


def validate_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            json.load(file)
        return True
    except json.JSONDecodeError as e:
        return False
    except Exception as e:
        return False
async def make_request(session: aiohttp.ClientSession, prompt: str, data: Dict, api_base: str):
    if "WebQA" in JSON_FILE_PATH:
        cache_file = f"{CACHE_DIR}/{data['Guid']}.json"
    else:
        cache_file = f"{CACHE_DIR}/{data['qid']}.json"

    if os.path.exists(cache_file):
        if validate_json_file(cache_file):
            return
        else:
            os.remove(cache_file)

    payload = {
        "model": "qwen2.5:72b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 1.0,
            "num_ctx": 10240
        }
    }

    async with session.post(api_base, json=payload) as response:
        if response.status == 200:
            result = await response.json()
            result['question'] = data
            if "WebQA" in JSON_FILE_PATH:
                with open(f"{CACHE_DIR}/{data['Guid']}.json", "w", encoding="utf-8") as file:
                    json.dump(result, file, ensure_ascii=False, indent=2)
            else:
                with open(f"{CACHE_DIR}/{data['qid']}.json", "w", encoding="utf-8") as file:
                    json.dump(result, file, ensure_ascii=False, indent=2)
        else:
            print(f"请求失败，状态码: {response.status}")


async def process_batch(session: aiohttp.ClientSession, template: str, json_data: List[Dict], start_index: int):
    tasks = []
    for i in range(start_index, min(start_index + CONCURRENCY, len(json_data))):
        if "WebQA" in JSON_FILE_PATH:
            prompt = template.replace("{question}", json_data[i]['Q'])
        else:
            prompt = template.replace("{question}", json_data[i]['question'])
        if i % 3 == 0:
            tasks.append(make_request(session, prompt, json_data[i], API_URL))
        else:
            tasks.append(make_request(session, prompt, json_data[i], API_URL_base))
    await asyncio.gather(*tasks)


async def main():
    template = GRAPH_PATTERN_PROMPT
    json_data = await load_json_data()
    total_batches = math.ceil(len(json_data) / CONCURRENCY)
    if "WebQA" in JSON_FILE_PATH:
        json_data = list(json_data.values())
        val_data = []
        for data in json_data:
            if data['split'] == 'val':
                val_data.append(data)

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(val_data), CONCURRENCY):
                await process_batch(session, template, val_data, i)
                current_batch = i // CONCURRENCY + 1
                progress_percentage = (current_batch / total_batches) * 100
    else:
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(json_data), CONCURRENCY):
                await process_batch(session, template, json_data, i)
                current_batch = i // CONCURRENCY + 1
                progress_percentage = (current_batch / total_batches) * 100
if __name__ == "__main__":
    asyncio.run(main())