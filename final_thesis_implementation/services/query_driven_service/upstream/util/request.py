import base64
import os
import re

import dashscope
import requests
import google.generativeai as genai
import PIL.Image
import time
import requests
from openai import OpenAI
import io
def text_request(prompt: str,  api_base: str, temperature=0.0):
    payload = {
        "model": "Qwen2.5-72B",
        "messages": [
            {
                "role": "user",
                "content": prompt}
        ],
        "stream": False,
        "max_tokens": 512,
        "stop": None,
        "temperature": 0.1,
        "top_p": 0.1,
        "top_k": 50,
        "frequency_penalty": 0.5,
        "n": 1,
        "response_format": {"type": "text"},
    }
    headers = {
        "Authorization": "Bearer ",
        "Content-Type": "application/json"
    }
    response = requests.request("POST", url="https://api.siliconflow.cn/v1/chat/completions", json=payload, headers=headers)
    if response.status_code == 200:
        # 修改这一行 - 从['response']改为['choices'][0]['message']['content']
        print(response.json()['choices'][0]['message']['content'])
        return response.json()['choices'][0]['message']['content']
    elif response.status_code == 429:
        # 修改这一行 - 从['response']改为['choices'][0]['message']['content']
        time.sleep(10)
        return text_request(prompt, api_base, temperature)
    else:
        print(f"请求失败，状态码: {response.status_code}")
        print(f"错误信息: {response.text}")  # 添加这行以显示更详细的错误信息

def llava_image_request(prompt, path, api_base, temperature=0.0):
    with open(path, 'rb') as image_file:
        imagedata = image_file.read()
    encoded_image = base64.b64encode(imagedata).decode('utf-8')
    images = [encoded_image]
    payload = {
        "model": "llava:34b",  # 使用llava:34b模型
        "num_ctx": 10240,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": images,
            }
        ],
        "stream": False,
    }

    response = requests.post(api_base, json=payload)

    if response.status_code == 200:
        return response.json()['message']['content']
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None

def gemini_select(prompt, image_paths, api_key=""):

   try:
       images = [PIL.Image.open(path) for path in image_paths]

       with requests.Session() as session:
           genai.configure(
               api_key=api_key,
               transport="rest",
               client_options={
                   "api_endpoint": "https://generativelanguage.googleapis.com"
               }
           )
           model = genai.GenerativeModel(model_name="gemini-1.5-flash")
           content = [prompt] + images
           response = model.generate_content(content)
           return response.text

   except Exception as e:
       return None

   finally:
       pattern = r"Description: (.*?)\n"
       match = re.search(pattern, prompt)

       if match:
           description = match.group(1)
       print(image_paths)
       print(response.text)