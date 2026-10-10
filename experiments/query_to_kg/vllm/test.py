import sys
import time
from pathlib import Path
from typing import Any, Callable

from litellm import completion, embedding

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.vllm_config import (  # noqa: E402
    API_KEY,
    CHAT_API_BASE,
    CHAT_MODEL,
    EMBED_API_BASE,
    EMBED_MODEL,
)

PROMPT = "Explain the core concept of GraphRAG."
EMBED_INPUT = "GraphRAG query to knowledge graph retrieval"
MAX_ATTEMPTS = 10
RETRY_DELAY_SECONDS = 10


def with_retries(label: str, operation: Callable[[], Any]) -> Any:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return operation()
        except Exception as error:  # pragma: no cover - depends on live local services
            last_error = error
            if attempt == MAX_ATTEMPTS:
                break
            print(
                f"{label} not ready yet "
                f"(attempt {attempt}/{MAX_ATTEMPTS}): {error}"
            )
            time.sleep(RETRY_DELAY_SECONDS)

    assert last_error is not None
    raise last_error


def run_completion():
    return completion(
        model=CHAT_MODEL,
        api_base=CHAT_API_BASE,
        api_key=API_KEY,
        messages=[
            {
                "role": "system",
                "content": "Return only the final contextual summary.",
            },
            {
                "role": "user",
                "content": PROMPT,
            },
        ],
        max_tokens=512,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def run_embedding():
    return embedding(
        model=EMBED_MODEL,
        api_base=EMBED_API_BASE,
        api_key=API_KEY,
        input=EMBED_INPUT,
    )


def main() -> None:
    resp = with_retries("chat model", run_completion)
    msg = resp.choices[0].message
    clean_content = msg.content.strip()

    print("CHAT:")
    print("model:", CHAT_MODEL)
    print("api_base:", CHAT_API_BASE)
    print("finish_reason:", resp.choices[0].finish_reason)
    print("content:", clean_content)

    emb = with_retries("embedding model", run_embedding)
    vec = emb.data[0]["embedding"]

    print("\nEMBEDDING:")
    print("model:", EMBED_MODEL)
    print("api_base:", EMBED_API_BASE)
    print("dimension:", len(vec))
    print("first 5:", vec[:5])


if __name__ == "__main__":
    main()
