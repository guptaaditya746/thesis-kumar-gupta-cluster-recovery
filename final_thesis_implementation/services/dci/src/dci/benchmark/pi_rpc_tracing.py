from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Span, Status, StatusCode, Tracer


MAX_CONTENT_ATTRIBUTE_CHARS = 32_000


def _truncate(value: str, *, limit: int = MAX_CONTENT_ATTRIBUTE_CHARS) -> str:
    if len(value) <= limit:
        return value
    omitted = len(value) - limit
    return f"{value[:limit]}\n[... {omitted} characters omitted]"


def _json_attribute(value: Any) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        rendered = repr(value)
    return _truncate(rendered)


def _string_attribute(value: Any) -> Optional[str]:
    if value is None:
        return None
    rendered = str(value).strip()
    return _truncate(rendered) if rendered else None


def _model_name(value: Any, fallback: Optional[str]) -> Optional[str]:
    if isinstance(value, str):
        return value or fallback
    if isinstance(value, dict):
        for key in ("id", "model", "name"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return fallback


def _provider_name(value: Any, fallback: Optional[str]) -> Optional[str]:
    if isinstance(value, dict):
        candidate = value.get("provider")
        if isinstance(candidate, str) and candidate:
            return candidate
    return fallback


def _message_text(message: Dict[str, Any]) -> str:
    parts = []
    for block in message.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") not in {"text", "thinking"}:
            continue
        text = block.get("text") or block.get("thinking")
        if isinstance(text, str) and text:
            parts.append(text)
    return _truncate("\n".join(parts))


def _set_if_present(span: Span, name: str, value: Any) -> None:
    if value is not None:
        span.set_attribute(name, value)


def _mark_error(span: Span, error_type: str, message: Optional[str] = None) -> None:
    span.set_status(Status(StatusCode.ERROR, _string_attribute(message)))
    span.set_attribute("error.type", error_type)
    if message:
        span.set_attribute("error.message", _truncate(message))


class PiRpcTraceBridge:
    """Translate Pi RPC lifecycle events into nested OpenTelemetry spans."""

    def __init__(
        self,
        *,
        tracer: Tracer,
        parent_context: Context,
        provider: Optional[str],
        model: Optional[str],
        capture_content: bool = False,
    ) -> None:
        self._tracer = tracer
        self._parent_context = parent_context
        self._provider = provider
        self._model = model
        self._capture_content = capture_content
        self._turn_index = 0
        self._turn_span: Optional[Span] = None
        self._turn_context: Optional[Context] = None
        self._llm_span: Optional[Span] = None
        self._tool_spans: Dict[str, Span] = {}
        self._disabled = False
        self._warned = False

    def record(self, event: Dict[str, Any]) -> None:
        """Consume one RPC event without ever interrupting the agent run."""
        if self._disabled:
            return
        try:
            self._record(event)
        except Exception as exc:
            if not self._warned:
                print(f"[langtrace] RPC event tracing disabled: {exc}", file=sys.stderr)
                self._warned = True
            self._disabled = True
            self._close_open_spans(error=f"trace bridge failure: {exc}")

    def close(self, *, error: Optional[str] = None) -> None:
        try:
            self._close_open_spans(error=error)
        except Exception as exc:
            if not self._warned:
                print(f"[langtrace] failed to close RPC spans: {exc}", file=sys.stderr)
                self._warned = True

    def _record(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "turn_start":
            self._start_turn()
        elif event_type == "provider_request_context":
            self._start_llm(event)
        elif event_type == "message_start":
            message = event.get("message") or {}
            if message.get("role") == "assistant" and self._llm_span is None:
                self._start_llm(event)
        elif event_type == "message_end":
            message = event.get("message") or {}
            if message.get("role") == "assistant":
                self._finish_llm(message)
        elif event_type == "tool_execution_start":
            self._start_tool(event)
        elif event_type == "tool_execution_end":
            self._finish_tool(event)
        elif event_type == "turn_end":
            self._finish_turn()
        elif event_type == "agent_end":
            self._finish_turn()

    def _ensure_turn(self) -> None:
        if self._turn_span is None:
            self._start_turn()

    def _start_turn(self) -> None:
        if self._turn_span is not None:
            self._finish_turn(error="new turn started before previous turn ended")
        self._turn_index += 1
        self._turn_span = self._tracer.start_span(
            "pi.turn",
            context=self._parent_context,
            attributes={"dci.pi.turn_index": self._turn_index},
        )
        self._turn_context = trace.set_span_in_context(
            self._turn_span,
            self._parent_context,
        )

    def _start_llm(self, event: Dict[str, Any]) -> None:
        self._ensure_turn()
        if self._llm_span is not None:
            _mark_error(
                self._llm_span,
                "overlapping_model_request",
                "new model request started before previous request ended",
            )
            self._llm_span.end()

        event_model = event.get("model")
        model = _model_name(event_model, self._model)
        provider = _provider_name(event_model, self._provider)
        request_index = event.get("requestIndex")
        messages = event.get("messages")
        attributes: Dict[str, Any] = {
            "gen_ai.operation.name": "chat",
            "dci.pi.turn_index": self._turn_index,
        }
        if provider:
            attributes["gen_ai.provider.name"] = provider
        if model:
            attributes["gen_ai.request.model"] = model
        if isinstance(request_index, int):
            attributes["dci.pi.request_index"] = request_index
        if isinstance(messages, list):
            attributes["dci.pi.message_count"] = len(messages)
            if self._capture_content:
                attributes["gen_ai.input.messages"] = _json_attribute(messages)

        self._llm_span = self._tracer.start_span(
            "pi.llm",
            context=self._turn_context or self._parent_context,
            attributes=attributes,
        )

    def _finish_llm(self, message: Dict[str, Any]) -> None:
        if self._llm_span is None:
            self._start_llm({"model": message.get("model")})
        assert self._llm_span is not None
        span = self._llm_span

        usage = message.get("usage") or {}
        cost = usage.get("cost") or {}
        _set_if_present(span, "gen_ai.provider.name", message.get("provider") or self._provider)
        _set_if_present(span, "gen_ai.response.model", message.get("model") or self._model)
        _set_if_present(span, "gen_ai.response.id", message.get("responseId"))
        _set_if_present(span, "gen_ai.response.finish_reason", message.get("stopReason"))
        _set_if_present(span, "gen_ai.usage.input_tokens", usage.get("input"))
        _set_if_present(span, "gen_ai.usage.output_tokens", usage.get("output"))
        _set_if_present(span, "dci.usage.total_tokens", usage.get("totalTokens"))
        _set_if_present(span, "dci.usage.cache_read_tokens", usage.get("cacheRead"))
        _set_if_present(span, "dci.usage.cache_write_tokens", usage.get("cacheWrite"))
        _set_if_present(span, "dci.cost.total_usd", cost.get("total"))

        content = message.get("content") or []
        if isinstance(content, list):
            content_types = [
                str(block.get("type"))
                for block in content
                if isinstance(block, dict) and block.get("type")
            ]
            if content_types:
                span.set_attribute("dci.pi.response_content_types", content_types)
        if self._capture_content:
            response_text = _message_text(message)
            if response_text:
                span.set_attribute("gen_ai.output.text", response_text)

        stop_reason = message.get("stopReason")
        if stop_reason in {"error", "aborted"}:
            _mark_error(span, f"model_{stop_reason}", f"model stop reason: {stop_reason}")
        span.end()
        self._llm_span = None

    def _start_tool(self, event: Dict[str, Any]) -> None:
        self._ensure_turn()
        tool_call_id = _string_attribute(event.get("toolCallId")) or "unknown"
        tool_name = _string_attribute(event.get("toolName")) or "unknown"
        existing = self._tool_spans.pop(tool_call_id, None)
        if existing is not None:
            _mark_error(existing, "duplicate_tool_start", "duplicate tool start event")
            existing.end()

        attributes: Dict[str, Any] = {
            "dci.tool.call_id": tool_call_id,
            "dci.tool.name": tool_name,
            "dci.pi.turn_index": self._turn_index,
        }
        if self._capture_content and "args" in event:
            attributes["dci.tool.arguments"] = _json_attribute(event.get("args"))
        self._tool_spans[tool_call_id] = self._tracer.start_span(
            f"pi.tool.{tool_name}",
            context=self._turn_context or self._parent_context,
            attributes=attributes,
        )

    def _finish_tool(self, event: Dict[str, Any]) -> None:
        tool_call_id = _string_attribute(event.get("toolCallId")) or "unknown"
        tool_name = _string_attribute(event.get("toolName")) or "unknown"
        span = self._tool_spans.pop(tool_call_id, None)
        if span is None:
            self._start_tool(event)
            span = self._tool_spans.pop(tool_call_id)

        is_error = bool(event.get("isError"))
        span.set_attribute("dci.tool.is_error", is_error)
        if self._capture_content and "result" in event:
            span.set_attribute("dci.tool.result", _json_attribute(event.get("result")))
        if is_error:
            _mark_error(span, "tool_execution_error", f"tool {tool_name} failed")
        span.end()

    def _finish_turn(self, *, error: Optional[str] = None) -> None:
        if self._turn_span is None:
            return
        if self._llm_span is not None:
            _mark_error(
                self._llm_span,
                "incomplete_model_request",
                error or "turn ended before model response completed",
            )
            self._llm_span.end()
            self._llm_span = None
        for tool_call_id, span in list(self._tool_spans.items()):
            _mark_error(span, "incomplete_tool_execution", error or "turn ended before tool completed")
            span.end()
            self._tool_spans.pop(tool_call_id, None)
        if error:
            _mark_error(self._turn_span, "pi_turn_error", error)
        self._turn_span.end()
        self._turn_span = None
        self._turn_context = None

    def _close_open_spans(self, *, error: Optional[str]) -> None:
        if self._llm_span is not None:
            _mark_error(
                self._llm_span,
                "incomplete_model_request",
                error or "trace closed before model response completed",
            )
            self._llm_span.end()
            self._llm_span = None
        for tool_call_id, span in list(self._tool_spans.items()):
            _mark_error(
                span,
                "incomplete_tool_execution",
                error or "trace closed before tool completed",
            )
            span.end()
            self._tool_spans.pop(tool_call_id, None)
        self._finish_turn(error=error)


class PiRpcTraceSession:
    """Own one query root span and its RPC-event bridge."""

    def __init__(
        self,
        *,
        provider: Optional[str],
        model: Optional[str],
        question: str,
        output_dir: str,
        capture_content: bool = False,
        tracer: Optional[Tracer] = None,
    ) -> None:
        self._tracer = tracer or trace.get_tracer("dci.pi_rpc")
        self._provider = provider
        self._model = model
        self._question = question
        self._output_dir = output_dir
        self._capture_content = capture_content
        self._root_span: Optional[Span] = None
        self._bridge: Optional[PiRpcTraceBridge] = None
        self._error: Optional[str] = None

    @property
    def trace_id(self) -> Optional[str]:
        if self._root_span is None:
            return None
        context = self._root_span.get_span_context()
        if not context.is_valid:
            return None
        return f"{context.trace_id:032x}"

    def start(self) -> None:
        if self._root_span is not None:
            return
        attributes: Dict[str, Any] = {
            "dci.output_dir": self._output_dir,
            "dci.question.characters": len(self._question),
        }
        if self._provider:
            attributes["gen_ai.provider.name"] = self._provider
        if self._model:
            attributes["gen_ai.request.model"] = self._model
        if self._capture_content:
            attributes["dci.question"] = _truncate(self._question)

        self._root_span = self._tracer.start_span("dci.pi.query", attributes=attributes)
        parent_context = trace.set_span_in_context(self._root_span)
        self._bridge = PiRpcTraceBridge(
            tracer=self._tracer,
            parent_context=parent_context,
            provider=self._provider,
            model=self._model,
            capture_content=self._capture_content,
        )

    def record(self, event: Dict[str, Any]) -> None:
        if self._bridge is not None:
            self._bridge.record(event)

    def complete(self, final_text: str) -> None:
        if self._root_span is None:
            return
        self._root_span.set_attribute("dci.run.status", "completed")
        self._root_span.set_attribute("dci.answer.characters", len(final_text))
        if self._capture_content and final_text:
            self._root_span.set_attribute("dci.answer", _truncate(final_text))

    def fail(self, error: BaseException | str) -> None:
        self._error = str(error)
        if self._root_span is not None:
            self._root_span.set_attribute("dci.run.status", "failed")
            _mark_error(self._root_span, type(error).__name__, self._error)

    def close(self) -> None:
        if self._bridge is not None:
            self._bridge.close(error=self._error)
            self._bridge = None
        if self._root_span is not None:
            self._root_span.end()
            self._root_span = None
