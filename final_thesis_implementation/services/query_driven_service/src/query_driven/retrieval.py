from __future__ import annotations

import asyncio
import json
import os
import re
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .config import ServiceConfig
from .corpus import (
    CorpusAdapter,
    CorpusDocument,
    FileCorpusAdapter,
    InvalidDocumentReference,
    build_corpus_adapter,
)
from .io import read_json, safe_id, write_json
from .logging import get_logger


@dataclass(slots=True)
class RetrievedDocument:
    document: CorpusDocument
    rank: int
    reason: str | None = None

    @property
    def document_id(self) -> str:
        return self.document.id

    @property
    def path(self) -> Path:
        return self.document.reference.path

    @property
    def text(self) -> str:
        return self.document.text


@dataclass(slots=True)
class RetrievalResult:
    query_id: str
    question: str
    documents: list[RetrievedDocument]
    raw_agent_output: str
    status: Literal["complete", "unfinalized"] = "complete"


_RETRIEVAL_BLOCK = re.compile(
    r"<retrieval_result>\s*(\{.*?\})\s*</retrieval_result>",
    re.IGNORECASE | re.DOTALL,
)


def retrieval_prompt(
    *,
    question: str,
    pattern: str,
    corpus: CorpusAdapter | None = None,
    corpus_root: Path | None = None,
    top_k: int,
    max_search_tools: int = 50,
    max_search_seconds: int = 300,
) -> str:
    if corpus is None:
        if corpus_root is None:
            raise ValueError("retrieval_prompt requires corpus or corpus_root")
        corpus = FileCorpusAdapter(root=corpus_root)
    output_example = json.dumps(corpus.output_example(), ensure_ascii=False, indent=6)
    return f"""You are retrieving evidence from a local corpus.

Use only the local corpus at {corpus.root}.
Search iteratively with filesystem tools such as rg, find, read, and bash.
Use ripgrep correctly: use one pattern with alternation, or repeated -e options; for example `rg -n -i -e "term1" -e "term2" .`. Do not write `rg term1 term2`; do not use `-r` for recursion; do not use `-f` unless you provide a pattern file.
The query-specific graph pattern is a retrieval hint, not evidence.
Derive useful entities, aliases, relations, and search terms from the question and pattern.
Begin with the shortest distinctive named entity or exact title in the question. Search the entity itself, not a natural-language phrase describing its relation.
Do not stop after one lexical match. Inspect promising records, refine searches, and rank genuinely useful documents.
If a search fails or is ambiguous, change the search terms instead of repeating the same call.
For multi-hop questions, identify and verify every link. Preserve the evidence for earlier hops while searching for later ones.
For a two-hop question, the final document list must retain at least one directly supporting record for each hop, normally at least two records. Do not replace earlier-hop evidence with the answer entity article.
A document reason may describe only facts explicitly visible in that selected record preview.
Return a document only when its inspected text directly supports a required hop. Never substitute general knowledge for evidence absent from the corpus.
Return at most {top_k} documents.
You have a search budget of {max_search_tools} tool executions and {max_search_seconds} seconds. Stop searching early enough to emit the final result.
Do not fabricate references. Every returned reference must identify evidence you actually inspected.
At the end, always emit the required <retrieval_result> JSON block, even if no documents are found.

{corpus.retrieval_instructions()}

Question:
{question}

Query Pattern:
{pattern}

At the end, return exactly this machine-readable section:
<retrieval_result>
{{
  "documents": [
{output_example}
  ]
}}
</retrieval_result>
"""


def _parse_payload(raw: str) -> dict[str, Any] | None:
    match = _RETRIEVAL_BLOCK.search(raw)
    if match:
        try:
            value = json.loads(match.group(1))
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("documents"), list):
            return value
    return None


def parse_retrieval_output(
    raw: str,
    *,
    query_id: str,
    question: str,
    corpus: CorpusAdapter | None = None,
    corpus_root: Path | None = None,
    top_k: int,
) -> RetrievalResult:
    if corpus is None:
        if corpus_root is None:
            raise ValueError("parse_retrieval_output requires corpus or corpus_root")
        corpus = FileCorpusAdapter(root=corpus_root)
    payload = _parse_payload(raw)
    documents: list[RetrievedDocument] = []
    seen: set[str] = set()
    for item in (payload or {}).get("documents", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        try:
            document = corpus.resolve(item)
        except (InvalidDocumentReference, OSError, ValueError) as exc:
            get_logger(stage="retrieval").warning(
                "invalid_retrieval_reference",
                query_id=query_id,
                path=item.get("path"),
                reason=str(exc),
            )
            continue
        document_id = document.id
        if document_id in seen:
            continue
        seen.add(document_id)
        try:
            rank = int(item.get("rank", len(documents) + 1))
        except (TypeError, ValueError):
            rank = len(documents) + 1
        documents.append(
            RetrievedDocument(
                document=document,
                rank=rank,
                reason=str(item["reason"]) if item.get("reason") is not None else None,
            )
        )
        if len(documents) >= top_k:
            break
    documents.sort(key=lambda item: (item.rank, item.document_id))
    return RetrievalResult(
        query_id=query_id,
        question=question,
        documents=documents,
        raw_agent_output=raw,
        status="complete" if payload is not None else "unfinalized",
    )


def _event_text(event: Any) -> list[str]:
    if not isinstance(event, dict) or event.get("type") != "message_end":
        return []
    message = event.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return []
    content = message.get("content", [])
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]



async def _run_pi(cfg: ServiceConfig, prompt: str, corpus_root: Path) -> str:
    cli = cfg.agent.package_dir / "dist" / "cli.js"
    if not cli.exists():
        raise FileNotFoundError(f"Pi coding-agent CLI was not found: {cli}")
    budget_extension = (
        Path(__file__).parent / "pi_extensions" / "retrieval-budget.mjs"
    )
    if not budget_extension.exists():
        raise FileNotFoundError(f"Pi retrieval budget extension was not found: {budget_extension}")
    command = [
        "node",
        str(cli),
        "--mode",
        "json",
        "--print",
        "--provider",
        cfg.agent.provider,
        "--model",
        cfg.agent.model,
        "--tools",
        ",".join(cfg.agent.tools),
        "--no-session",
        "--no-extensions",
        "--extension",
        str(budget_extension),
    ]
    if cfg.agent.thinking:
        command.extend(["--thinking", cfg.agent.thinking])
    if cfg.agent.context_management_level:
        command.extend(["--context-management-level", cfg.agent.context_management_level])
    command.append(prompt)

    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(cfg.agent.agent_dir)
    env["PI_JSON_EVENT_MODE"] = "essential"
    env["QD_SEARCH_MAX_TOOLS"] = str(cfg.retrieval.max_search_turns)
    env["QD_SEARCH_MAX_SECONDS"] = str(cfg.retrieval.max_search_seconds)
    env["QD_MAX_OUTPUT_TOKENS"] = str(cfg.agent.max_output_tokens)
    env["QD_CORPUS_FILE"] = cfg.dataset.corpus_file or ""
    env["QD_DOCUMENT_ID_FIELD"] = cfg.dataset.document_id_field
    env["QD_DOCUMENT_CONTENT_FIELD"] = cfg.dataset.document_content_field
    env["QD_MAX_DOCUMENT_BYTES"] = str(cfg.dataset.max_document_bytes)
    heap = f"--max-old-space-size={cfg.agent.node_max_old_space_size_mb}"
    env["NODE_OPTIONS"] = f"{env.get('NODE_OPTIONS', '').strip()} {heap}".strip()

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(corpus_root),
        env=env,
        limit=16 * 1024 * 1024,
        start_new_session=True,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdout is not None and process.stderr is not None
    stderr_task = asyncio.create_task(process.stderr.read())
    text_events: list[str] = []
    completed_tools = 0
    assistant_error: str | None = None
    loop = asyncio.get_running_loop()
    hard_deadline = loop.time() + (
        cfg.retrieval.max_search_seconds + cfg.retrieval.finalization_grace_seconds
    )
    timed_out = False
    while True:
        remaining = hard_deadline - loop.time()
        if remaining <= 0:
            timed_out = True
            break
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
        except TimeoutError:
            timed_out = True
            break
        if not line:
            break
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        text_events.extend(_event_text(event))
        if isinstance(event, dict) and event.get("type") == "message_end":
            message = event.get("message", {})
            if (
                isinstance(message, dict)
                and message.get("role") == "assistant"
                and message.get("stopReason") == "error"
            ):
                assistant_error = str(message.get("errorMessage", "unknown model error"))
        if isinstance(event, dict) and event.get("type") == "tool_execution_end":
            completed_tools += 1
        if (
            cfg.retrieval.show_tools
            and isinstance(event, dict)
            and event.get("type") == "tool_execution_start"
        ):
            args = json.dumps(event.get("args", {}), ensure_ascii=False)
            get_logger(stage="retrieval").info(
                "retrieval_tool_started",
                tool=event.get("toolName"),
                args=args[:1000],
            )
    if timed_out and process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(process.wait(), timeout=5.0)
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
    stderr = await stderr_task
    if timed_out:
        get_logger(stage="retrieval").warning(
            "retrieval_hard_timeout",
            max_search_seconds=cfg.retrieval.max_search_seconds,
            finalization_grace_seconds=cfg.retrieval.finalization_grace_seconds,
        )
    get_logger(stage="retrieval").info(
        "retrieval_agent_finished",
        completed_tools=completed_tools,
        timed_out=timed_out,
    )
    if assistant_error and not timed_out:
        raise RuntimeError(f"Pi retrieval model failed: {assistant_error[-2000:]}")
    if not timed_out and process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"Pi retrieval agent failed with exit code {process.returncode}: {detail[-2000:]}"
        )
    return "\n".join(text_events).strip()


def _saved_result(path: Path, *, corpus: CorpusAdapter, top_k: int) -> RetrievalResult | None:
    if not path.exists():
        return None
    try:
        value = read_json(path)
        if value.get("corpus_fingerprint") != corpus.fingerprint():
            return None
        documents: list[RetrievedDocument] = []
        for item in value.get("documents", []):
            if not isinstance(item, dict):
                return None
            document = corpus.resolve(item)
            documents.append(
                RetrievedDocument(
                    document=document,
                    rank=int(item.get("rank", len(documents) + 1)),
                    reason=item.get("reason"),
                )
            )
        status: Literal["complete", "unfinalized"] = (
            "unfinalized" if value.get("status") == "unfinalized" else "complete"
        )
        return RetrievalResult(
            query_id=str(value["query_id"]),
            question=str(value.get("question", "")),
            documents=documents[:top_k],
            raw_agent_output=(
                (path.parent / "retrieval_raw.txt").read_text(encoding="utf-8")
                if (path.parent / "retrieval_raw.txt").exists()
                else ""
            ),
            status=status,
        )
    except (
        InvalidDocumentReference,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ):
        return None


async def run_retrieval_stage(
    cfg: ServiceConfig,
    questions: list[dict[str, Any]],
    corpus_root: Path | None,
) -> dict[str, RetrievalResult]:
    if not cfg.retrieval.enabled:
        raise ValueError("Retrieval is disabled")
    if corpus_root is None:
        raise ValueError("dataset.corpus_root is required for agent retrieval")
    corpus_root = corpus_root.resolve()
    if not corpus_root.is_dir():
        raise ValueError(f"dataset.corpus_root is not a directory: {corpus_root}")
    corpus = build_corpus_adapter(cfg.dataset, root=corpus_root)

    logger = get_logger(stage="retrieval")
    semaphore = asyncio.Semaphore(cfg.runtime.concurrency)

    async def one(question: dict[str, Any]) -> RetrievalResult:
        raw_qid = str(question[cfg.dataset.qid_field])
        qid = safe_id(raw_qid)
        query = str(question[cfg.dataset.question_field])
        out_dir = cfg.runtime.output_root / "retrieval" / qid
        retrieval_path = out_dir / "retrieval.json"
        if cfg.runtime.resume and not cfg.runtime.overwrite:
            cached = _saved_result(
                retrieval_path,
                corpus=corpus,
                top_k=cfg.retrieval.top_k,
            )
            if cached is not None:
                logger.info("retrieval_resumed", qid=raw_qid, retrieved_count=len(cached.documents))
                return cached

        pattern = ""
        if cfg.retrieval.use_query_pattern:
            pattern_path = cfg.runtime.output_root / "pattern" / f"{qid}.json"
            if pattern_path.exists():
                pattern_value = read_json(pattern_path)
                pattern = str(pattern_value.get("response", ""))
        prompt = retrieval_prompt(
            question=query,
            pattern=pattern,
            corpus=corpus,
            top_k=cfg.retrieval.top_k,
            max_search_tools=cfg.retrieval.max_search_turns,
            max_search_seconds=cfg.retrieval.max_search_seconds,
        )
        logger.info("retrieval_started", qid=raw_qid, corpus_root=str(corpus_root))
        async with semaphore:
            raw = await _run_pi(cfg, prompt, corpus_root)
            logger.info("retrieval_raw_debug", qid=raw_qid, raw_length=len(raw), has_retrieval_block="<retrieval_result>" in raw)
        result = parse_retrieval_output(
            raw,
            query_id=raw_qid,
            question=query,
            corpus=corpus,
            top_k=cfg.retrieval.top_k,
        )
        if not result.documents:
            logger.warning("retrieval_parse_empty", qid=raw_qid)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "retrieval_raw.txt").write_text(raw, encoding="utf-8")
        write_json(
            out_dir / "retrieval.json",
            {
                "query_id": result.query_id,
                "question": result.question,
                "status": result.status,
                "corpus_fingerprint": corpus.fingerprint(),
                "documents": [
                    {
                        **item.document.reference.to_jsonable(),
                        "rank": item.rank,
                        "reason": item.reason,
                    }
                    for item in result.documents
                ],
            },
        )
        logger.info(
            "retrieval_completed",
            qid=raw_qid,
            retrieved_count=len(result.documents),
            status=result.status,
        )
        return result

    results = await asyncio.gather(*(one(question) for question in questions))
    by_qid = {result.query_id: result for result in results}
    write_json(
        cfg.runtime.output_root / "retrieved_ids.json",
        {
            qid: [item.document_id for item in result.documents]
            for qid, result in by_qid.items()
        },
    )
    with (cfg.runtime.output_root / "retrieval_results.jsonl").open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(
                json.dumps(
                    {
                        "query_id": result.query_id,
                        "status": result.status,
                        "documents": [
                            {
                                **item.document.reference.to_jsonable(),
                                "rank": item.rank,
                            }
                            for item in result.documents
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return by_qid
