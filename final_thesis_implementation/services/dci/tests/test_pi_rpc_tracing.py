from __future__ import annotations

import unittest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from dci.benchmark.pi_rpc_tracing import PiRpcTraceBridge


class PiRpcTraceBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = provider.get_tracer("dci.tests")
        self.root_span = self.tracer.start_span("dci.pi.query")
        self.root_context = trace.set_span_in_context(self.root_span)

    def tearDown(self) -> None:
        if self.root_span.is_recording():
            self.root_span.end()

    def test_reconstructs_turn_llm_and_tool_spans(self) -> None:
        bridge = PiRpcTraceBridge(
            tracer=self.tracer,
            parent_context=self.root_context,
            provider="vllm",
            model="qwen-chat",
        )

        bridge.record({"type": "turn_start"})
        bridge.record(
            {
                "type": "provider_request_context",
                "requestIndex": 1,
                "model": {"provider": "vllm", "id": "qwen-chat"},
                "messages": [{"role": "user", "content": "question"}],
            }
        )
        bridge.record(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "provider": "vllm",
                    "model": "qwen-chat",
                    "content": [{"type": "toolCall"}],
                    "usage": {
                        "input": 120,
                        "output": 30,
                        "cacheRead": 10,
                        "cacheWrite": 2,
                        "totalTokens": 150,
                        "cost": {"total": 0.001},
                    },
                    "stopReason": "toolUse",
                    "responseId": "response-1",
                },
            }
        )
        bridge.record(
            {
                "type": "tool_execution_start",
                "toolCallId": "tool-1",
                "toolName": "grep",
                "args": {"pattern": "kinase"},
            }
        )
        bridge.record(
            {
                "type": "tool_execution_end",
                "toolCallId": "tool-1",
                "toolName": "grep",
                "isError": False,
                "result": {"content": [{"type": "text", "text": "match"}]},
            }
        )
        bridge.record({"type": "turn_end"})
        bridge.record({"type": "agent_end"})
        bridge.close()
        self.root_span.end()

        spans = {span.name: span for span in self.exporter.get_finished_spans()}
        self.assertEqual(
            {"dci.pi.query", "pi.turn", "pi.llm", "pi.tool.grep"},
            set(spans),
        )
        self.assertEqual(
            spans["dci.pi.query"].context.span_id,
            spans["pi.turn"].parent.span_id,
        )
        self.assertEqual(
            spans["pi.turn"].context.span_id,
            spans["pi.llm"].parent.span_id,
        )
        self.assertEqual(
            spans["pi.turn"].context.span_id,
            spans["pi.tool.grep"].parent.span_id,
        )
        self.assertEqual(120, spans["pi.llm"].attributes["gen_ai.usage.input_tokens"])
        self.assertEqual(30, spans["pi.llm"].attributes["gen_ai.usage.output_tokens"])
        self.assertEqual("qwen-chat", spans["pi.llm"].attributes["gen_ai.request.model"])
        self.assertFalse(spans["pi.tool.grep"].attributes["dci.tool.is_error"])

    def test_close_marks_unfinished_spans_as_errors(self) -> None:
        bridge = PiRpcTraceBridge(
            tracer=self.tracer,
            parent_context=self.root_context,
            provider="vllm",
            model="qwen-chat",
        )
        bridge.record({"type": "turn_start"})
        bridge.record(
            {
                "type": "tool_execution_start",
                "toolCallId": "tool-open",
                "toolName": "read",
            }
        )

        bridge.close(error="RPC process exited")
        self.root_span.end()

        spans = {span.name: span for span in self.exporter.get_finished_spans()}
        self.assertEqual("ERROR", spans["pi.tool.read"].status.status_code.name)
        self.assertEqual("ERROR", spans["pi.turn"].status.status_code.name)


if __name__ == "__main__":
    unittest.main()
