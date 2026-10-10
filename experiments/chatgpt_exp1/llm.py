# llm.py
import json
from openai import OpenAI
from typing import Optional, Dict, Any

_client = None

def get_client(base_url: str, api_key: str = "EMPTY") -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=base_url, api_key=api_key)
    return _client

def llm_json(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
    schema_hint: Optional[dict] = None,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """Call local vLLM (OpenAI-compatible) and return parsed JSON dict."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    # Optional: if your vLLM supports JSON schema output
    if schema_hint:
        kwargs["response_format"] = {"type": "json_schema", "json_schema": schema_hint}

    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content

    try:
        return json.loads(text)
    except Exception as e:
        raise RuntimeError(f"Failed to parse JSON.\nRaw LLM output:\n{text}") from e
