import json
import logging
from typing import Any, List

from backend.app.extraction.prompts import KG_EXTRACTION_PROMPT
from backend.app.extraction.query_understanding import QueryIntent
from backend.app.llm_config import API_KEY, CHAT_API_BASE, CHAT_MODEL
from backend.app.retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 2048
RETRY_MAX_TOKENS = 4096

try:
    from litellm import completion
except ImportError as exc:
    raise RuntimeError("LiteLLM is not installed; please run `pip install litellm`") from exc


class KGExtractor:
    """
    Service for extracting query-specific knowledge graph patches from retrieved chunks.
    """

    def __init__(self, model: str = CHAT_MODEL, api_base: str = CHAT_API_BASE, api_key: str = API_KEY):
        self.model = model
        self.api_base = api_base
        self.api_key = api_key

    def _format_chunks(self, chunks: List[RetrievedChunk]) -> str:
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            formatted.append(f"--- Chunk {i} ---")
            formatted.append(f"Chunk ID: {chunk.chunk_id}")
            formatted.append(f"Paper ID: {chunk.paper_id}")
            formatted.append(f"Paper Title: {chunk.paper_title}")
            formatted.append(f"Section Title: {chunk.section_title}")
            formatted.append(f"Raw Text:\n{chunk.raw_text}")
            formatted.append("")
        return "\n".join(formatted)

    @staticmethod
    def _clean_content(content: str) -> str:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    @staticmethod
    def _is_likely_truncated(content: str, finish_reason: Any) -> bool:
        if finish_reason == "length":
            return True
        return content.count("{") > content.count("}") or content.count("[") > content.count("]")

    def _request_completion(self, prompt: str, *, max_tokens: int, system_content: str) -> Any:
        return completion(
            model=self.model,
            api_base=self.api_base,
            api_key=self.api_key,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

    def extract_graph_patch(self, question: str, intent: QueryIntent, retrieved_chunks: List[RetrievedChunk]) -> dict[str, Any]:
        """
        Extracts a query-specific knowledge graph patch from retrieved chunks.
        Returns the raw parsed JSON dict for validation and cleaning.
        Raises an exception if the output is not valid JSON.
        """
        chunks_context = self._format_chunks(retrieved_chunks)
        needed_nodes = [n.value for n in intent.needed_node_types]
        needed_edges = [e.value for e in intent.needed_edge_types]

        prompt = KG_EXTRACTION_PROMPT.format(
            question=question,
            intent_type=intent.intent_type,
            needed_node_types=", ".join(needed_nodes),
            needed_edge_types=", ".join(needed_edges),
            chunks_context=chunks_context,
        )
        system_content = (
            "You are a scientific knowledge graph extraction system. Return strictly valid JSON "
            "without Markdown blocks or any conversational text. Extract only the smallest graph "
            "patch needed to answer the question, keeping the output compact."
        )
        retry_system_content = (
            "You previously returned output that could not be parsed. Return a smaller result as "
            "strictly valid JSON only. Keep it compact: no more than 12 nodes and 16 edges."
        )

        try:
            attempts = [
                (system_content, DEFAULT_MAX_TOKENS),
                (retry_system_content, RETRY_MAX_TOKENS),
            ]
            last_error: json.JSONDecodeError | None = None

            for index, (attempt_system_content, max_tokens) in enumerate(attempts, start=1):
                response = self._request_completion(
                    prompt,
                    max_tokens=max_tokens,
                    system_content=attempt_system_content,
                )

                choice = response.choices[0]
                content = choice.message.content
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Model returned empty content.")

                content = self._clean_content(content)

                try:
                    return json.loads(content)
                except json.JSONDecodeError as error:
                    last_error = error
                    finish_reason = getattr(choice, "finish_reason", None)
                    logger.warning(
                        "Failed to parse KG extraction JSON on attempt %s/%s (finish_reason=%r): %s",
                        index,
                        len(attempts),
                        finish_reason,
                        error,
                    )
                    if index == len(attempts) or not self._is_likely_truncated(content, finish_reason):
                        logger.error(f"Failed to parse LLM output as JSON. Output was: {content}")
                        raise ValueError(f"Invalid or unparsable extraction output: {error}") from error

            if last_error is not None:
                raise ValueError(f"Invalid or unparsable extraction output: {last_error}") from last_error
            raise ValueError("Invalid or unparsable extraction output: unknown parsing failure")

        except Exception as e:
            logger.error(f"KG extraction failed: {e}")
            raise
