import os
from litellm import completion, embedding

chat = completion(
    model="openai/qwen-chat",
    api_base="http://127.0.0.1:8000/v1",
    api_key=os.getenv("VLLM_API_KEY", ""),
    messages=[{"role": "user", "content": "Hello"}],
)

emb = embedding(
    model="openai/qwen-embed",
    api_base="http://127.0.0.1:8001/v1",
    api_key=os.getenv("VLLM_API_KEY", ""),
    input=["GraphRAG query to knowledge graph retrieval"],
)
