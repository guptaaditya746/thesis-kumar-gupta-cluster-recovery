from typing import Any

from pydantic import BaseModel, Field
from rdflib import Graph, Literal, URIRef


class SPARQLExecutionResult(BaseModel):
    status: str
    row_count: int
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class SPARQLExecutor:
    """Execute safe SELECT queries against a local RDFLib graph."""

    def execute(self, graph: Graph, query: str) -> SPARQLExecutionResult:
        try:
            result = graph.query(query)
            columns = [str(variable) for variable in result.vars]
            rows: list[dict[str, Any]] = []

            for row in result:
                if hasattr(row, "asdict"):
                    row_data = {str(key): value for key, value in row.asdict().items()}
                else:
                    row_data = {}
                if not row_data:
                    row_data = {
                        column: row[index]
                        for index, column in enumerate(columns)
                    }
                rows.append(
                    {
                        column: self._serialize_term(row_data.get(column))
                        for column in columns
                    }
                )

            return SPARQLExecutionResult(
                status="success",
                row_count=len(rows),
                columns=columns,
                rows=rows,
            )
        except Exception as exc:
            return SPARQLExecutionResult(
                status="error",
                row_count=0,
                columns=[],
                rows=[],
                error=self._format_error(exc),
            )

    @staticmethod
    def _serialize_term(term: Any) -> Any:
        if term is None:
            return None
        if isinstance(term, Literal):
            return term.toPython()
        if isinstance(term, URIRef):
            return str(term)
        return str(term)

    @staticmethod
    def _format_error(error: Exception) -> str:
        error_text = str(error)
        if "Expected" in error_text or "Parse" in type(error).__name__:
            return f"SPARQL parse error: {error_text}"
        return f"SPARQL execution error: {error_text}"


def execute_sparql(graph: Graph, query: str) -> SPARQLExecutionResult:
    return SPARQLExecutor().execute(graph, query)
