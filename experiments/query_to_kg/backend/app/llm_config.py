import os
from llama_index.embeddings.litellm import LiteLLMEmbedding

API_KEY = os.getenv("VLLM_API_KEY", "")

CHAT_MODEL = "openai/qwen-chat"
CHAT_API_BASE = "http://127.0.0.1:8000/v1"

EMBED_MODEL = "openai/qwen-embed"
EMBED_API_BASE = "http://127.0.0.1:8001/v1"


def build_embedding_model() -> LiteLLMEmbedding:
    return LiteLLMEmbedding(
        model_name=EMBED_MODEL,
        api_base=EMBED_API_BASE,
        api_key=API_KEY,
    )
