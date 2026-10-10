from typing import Any

from backend.app.answering.schemas import TraceStep
from backend.app.query_generation.schema_context import SchemaContext
from backend.app.query_generation.sparql_validator import SPARQLValidationResult
from backend.app.rdf.sparql_executor import SPARQLExecutionResult


class TraceBuilder:
    """Build the step-by-step answering trace returned by the backend."""

    @staticmethod
    def graph_patch_received(*, node_count: int, edge_count: int) -> TraceStep:
        return TraceStep(
            step="graph_patch_received",
            details={
                "node_count": node_count,
                "edge_count": edge_count,
            },
        )

    @staticmethod
    def rdf_materialized(*, triple_count: int, serialization: str) -> TraceStep:
        return TraceStep(
            step="rdf_materialized",
            details={
                "triple_count": triple_count,
                "serialization": serialization,
            },
        )

    @staticmethod
    def schema_context_built(schema_context: SchemaContext) -> TraceStep:
        return TraceStep(
            step="schema_context_built",
            details={
                "classes": schema_context.observed_classes,
                "predicates": schema_context.observed_predicates,
            },
        )

    @staticmethod
    def sparql_generated(query: str) -> TraceStep:
        return TraceStep(step="sparql_generated", details=query)

    @staticmethod
    def sparql_validated(validation: SPARQLValidationResult) -> TraceStep:
        return TraceStep(
            step="sparql_validated",
            details=validation.model_dump(),
        )

    @staticmethod
    def sparql_repaired(*, failed_query: str, repaired_query: str, error: str | None) -> TraceStep:
        return TraceStep(
            step="sparql_repaired",
            details={
                "failed_query": failed_query,
                "repaired_query": repaired_query,
                "error": error,
            },
        )

    @staticmethod
    def sparql_executed(result: SPARQLExecutionResult) -> TraceStep:
        details: dict[str, Any] = {
            "status": result.status,
            "row_count": result.row_count,
        }
        if result.error:
            details["error"] = result.error
        return TraceStep(step="sparql_executed", details=details)

    @staticmethod
    def answer_generated(answer: str) -> TraceStep:
        return TraceStep(step="answer_generated", details=answer)

    @staticmethod
    def build(steps: list[TraceStep]) -> list[dict[str, Any]]:
        return [step.model_dump() for step in steps]
