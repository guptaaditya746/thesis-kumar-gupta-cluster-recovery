from __future__ import annotations

import asyncio
import base64
import hashlib
import os
from pathlib import Path
from typing import Any

import httpx

from .config import EmbeddingConfig, ImageSelectorConfig, TextModelConfig, VisionConfig
from .io import read_json, write_json


class TextClient:
    def __init__(self, config: TextModelConfig) -> None:
        self.config = config

    async def generate(self, prompt: str) -> str:
        headers = dict(self.config.extra_headers)
        if self.config.kind == "openai_compatible":
            key = os.environ.get(self.config.api_key_env, "").strip()
            if key:
                headers.setdefault("Authorization", f"Bearer {key}")
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "max_tokens": self.config.max_tokens,
            }
        else:
            payload = {
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                },
            }

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(self.config.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if self.config.kind == "openai_compatible":
            return str(data["choices"][0]["message"]["content"])
        if isinstance(data.get("response"), str):
            return data["response"]
        if isinstance(data.get("message"), dict):
            return str(data["message"].get("content", ""))
        raise RuntimeError("Text model response did not contain response text")


class EmbeddingClient:
    def __init__(self, config: EmbeddingConfig, cache_root: Path) -> None:
        self.config = config
        self.cache_root = config.cache_dir or (cache_root / "embeddings")

    async def embed(self, text: str) -> list[float]:
        if not self.config.enabled:
            raise RuntimeError("Embedding service is disabled")
        digest = hashlib.sha256((self.config.model + "\0" + text).encode("utf-8")).hexdigest()
        cache = self.cache_root / f"{digest}.json"
        if cache.exists():
            payload = read_json(cache)
            return [float(v) for v in payload["embedding"]]

        request = {"model": self.config.model, "input": text}
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(self.config.endpoint, json=request)
            response.raise_for_status()
            data = response.json()
        vector = data.get("embedding")
        if vector is None and isinstance(data.get("data"), list) and data["data"]:
            vector = data["data"][0].get("embedding")
        if vector is None and isinstance(data.get("embeddings"), list):
            embeddings = data["embeddings"]
            vector = embeddings[0] if embeddings and isinstance(embeddings[0], list) else embeddings
        if not isinstance(vector, list):
            raise RuntimeError("Embedding response did not contain an embedding vector")
        result = [float(v) for v in vector]
        write_json(cache, {"model": self.config.model, "embedding": result})
        return result


class VisionClient:
    def __init__(self, config: VisionConfig) -> None:
        self.config = config

    async def answer(self, *, prompt: str, image_path: Path) -> str | None:
        if not self.config.enabled:
            return None
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(self.config.endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        if isinstance(data.get("message"), dict):
            return str(data["message"].get("content", ""))
        if isinstance(data.get("response"), str):
            return data["response"]
        return None


class ImageSelector:
    def __init__(self, config: ImageSelectorConfig) -> None:
        self.config = config

    async def select(self, prompt: str, image_paths: list[Path]) -> int:
        if not image_paths:
            raise ValueError("No images supplied")
        if self.config.kind == "first" or len(image_paths) == 1:
            return 0

        def _gemini() -> int:
            try:
                import google.generativeai as genai
                from PIL import Image
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("Install the 'multimodal' extra to use Gemini image selection") from exc
            api_key = os.environ.get(self.config.api_key_env, "").strip()
            if not api_key:
                raise RuntimeError(f"Missing Gemini key in {self.config.api_key_env}")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name=self.config.model)
            images = [Image.open(path) for path in image_paths]
            response = model.generate_content([prompt, *images]).text.lower().replace(" ", "")
            for index in range(min(3, len(image_paths))):
                if f"answer:{index + 1}" in response:
                    return index
            return 0

        return await asyncio.to_thread(_gemini)
