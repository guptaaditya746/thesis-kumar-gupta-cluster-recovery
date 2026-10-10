import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import Graph

from backend.app.answering.answer_generator import AnswerGenerator
from backend.app.answering.schemas import AnswerResponse, EvidenceRecord
from backend.app.answering.trace_builder import TraceBuilder
from backend.app.extraction.schemas import GraphPatch, NodeType
from backend.app.query_generation.schema_context import (
    SchemaContext,
    SchemaContextBuilder,
    build_graph_summary,
)
from backend.app.query_generation.sparql_generator import SPARQLGenerator
from backend.app.query_generation.sparql_validator import (
    SPARQLValidationResult,
    SPARQLValidator,
)
from backend.app.rdf.rdf_builder import RDFBuilder
from backend.app.rdf.sparql_executor import SPARQLExecutionResult, SPARQLExecutor

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RDF_PATH = PROJECT_ROOT / "backend/app/data/rdf/latest_graph.ttl"
DEFAULT_SPARQL_PATH = PROJECT_ROOT / "backend/app/data/sparql/latest_query.rq"
DEFAULT_ANSWER_PATH = PROJECT_ROOT / "backend/app/data/answers/latest_answer.json"


@dataclass
class AnsweringRunContext:
    rdf_graph: Graph
    schema_context: SchemaContext
    graph_summary: str
    validation: SPARQLValidationResult
    query_result: SPARQLExecutionResult
    triple_count: int


class AnsweringService:
    """End-to-end RDF, SPARQL, and grounded answering pipeline."""

    def __init__(
        self,
        *,
        rdf_builder: RDFBuilder | None = None,
        schema_context_builder: SchemaContextBuilder | None = None,
        sparql_generator: SPARQLGenerator | None = None,
        sparql_validator: SPARQLValidator | None = None,
        sparql_executor: SPARQLExecutor | None = None,
        answer_generator: AnswerGenerator | None = None,
        trace_builder: TraceBuilder | None = None,
    ):
        self.rdf_builder = rdf_builder or RDFBuilder()
        self.schema_context_builder = schema_context_builder or SchemaContextBuilder()
        self.sparql_generator = sparql_generator or SPARQLGenerator()
        self.sparql_validator = sparql_validator or SPARQLValidator()
        self.sparql_executor = sparql_executor or SPARQLExecutor()
        self.answer_generator = answer_generator or AnswerGenerator()
        self.trace_builder = trace_builder or TraceBuilder()
        self.last_run_context: AnsweringRunContext | None = None

    def answer_from_graph_patch(
        self,
        question: str,
        graph_patch: GraphPatch | dict[str, Any],
    ) -> dict[str, Any]:
        patch = graph_patch if isinstance(graph_patch, GraphPatch) else GraphPatch(**graph_patch)
        trace_steps = [
            self.trace_builder.graph_patch_received(
                node_count=len(patch.nodes),
                edge_count=len(patch.edges),
            )
        ]

        rdf_graph = self.rdf_builder.build(patch)
        triple_count = len(rdf_graph)
        self.rdf_builder.serialize(rdf_graph, DEFAULT_RDF_PATH)
        trace_steps.append(
            self.trace_builder.rdf_materialized(
                triple_count=triple_count,
                serialization=self._relative_path(DEFAULT_RDF_PATH),
            )
        )

        schema_context = self.schema_context_builder.build(patch)
        trace_steps.append(self.trace_builder.schema_context_built(schema_context))
        graph_summary = build_graph_summary(patch)

        sparql_query = self.sparql_generator.generate(question, schema_context, patch)
        self._write_text(DEFAULT_SPARQL_PATH, sparql_query)
        trace_steps.append(self.trace_builder.sparql_generated(sparql_query))

        validation = self.sparql_validator.validate(sparql_query)
        trace_steps.append(self.trace_builder.sparql_validated(validation))

        if not validation.valid:
            query_result = SPARQLExecutionResult(
                status="validation_error",
                row_count=0,
                columns=[],
                rows=[],
                error="; ".join(validation.errors),
            )
            answer = "I could not generate a valid SPARQL query for this graph patch."
            trace_steps.append(self.trace_builder.answer_generated(answer))
            response = self._build_response(
                answer=answer,
                query=sparql_query,
                query_result=query_result,
                evidence=[],
                trace_steps=trace_steps,
            )
            self._save_response(response)
            self.last_run_context = AnsweringRunContext(
                rdf_graph=rdf_graph,
                schema_context=schema_context,
                graph_summary=graph_summary,
                validation=validation,
                query_result=query_result,
                triple_count=triple_count,
            )
            return response

        query_result = self.sparql_executor.execute(rdf_graph, sparql_query)
        if query_result.status == "error":
            repaired_query = self.sparql_generator.repair(sparql_query, query_result.error)
            if repaired_query != sparql_query:
                trace_steps.append(
                    self.trace_builder.sparql_repaired(
                        failed_query=sparql_query,
                        repaired_query=repaired_query,
                        error=query_result.error,
                    )
                )
                repaired_validation = self.sparql_validator.validate(repaired_query)
                trace_steps.append(self.trace_builder.sparql_validated(repaired_validation))
                if repaired_validation.valid:
                    sparql_query = repaired_query
                    self._write_text(DEFAULT_SPARQL_PATH, sparql_query)
                    validation = repaired_validation
                    query_result = self.sparql_executor.execute(rdf_graph, sparql_query)

        trace_steps.append(self.trace_builder.sparql_executed(query_result))
        evidence = self._extract_evidence(patch, query_result)
        answer = self.answer_generator.generate(
            question=question,
            sparql_query=sparql_query,
            query_result=query_result.model_dump(),
            evidence=evidence,
        )
        trace_steps.append(self.trace_builder.answer_generated(answer))

        response = self._build_response(
            answer=answer,
            query=sparql_query,
            query_result=query_result,
            evidence=evidence,
            trace_steps=trace_steps,
        )
        self._save_response(response)
        self.last_run_context = AnsweringRunContext(
            rdf_graph=rdf_graph,
            schema_context=schema_context,
            graph_summary=graph_summary,
            validation=validation,
            query_result=query_result,
            triple_count=triple_count,
        )
        return response

    @staticmethod
    def _extract_evidence(
        patch: GraphPatch,
        query_result: SPARQLExecutionResult,
    ) -> list[EvidenceRecord]:
        if query_result.status != "success":
            return []

        evidence_texts = {
            row.get("evidenceText")
            for row in query_result.rows
            if row.get("evidenceText")
        }

        records: list[EvidenceRecord] = []
        for node in patch.nodes:
            if node.type != NodeType.EVIDENCE:
                continue
            node_text = str(node.properties.get("text") or node.provenance.text_span)
            if evidence_texts and node_text not in evidence_texts:
                continue
            records.append(
                EvidenceRecord(
                    paper_id=node.provenance.paper_id,
                    paper_title=node.provenance.paper_title,
                    section_title=node.provenance.section_title,
                    chunk_id=node.provenance.chunk_id,
                    text_span=node_text,
                )
            )

        if records:
            return records

        for node in patch.nodes:
            if node.type == NodeType.EVIDENCE:
                records.append(
                    EvidenceRecord(
                        paper_id=node.provenance.paper_id,
                        paper_title=node.provenance.paper_title,
                        section_title=node.provenance.section_title,
                        chunk_id=node.provenance.chunk_id,
                        text_span=str(node.properties.get("text") or node.provenance.text_span),
                    )
                )
        return records

    def _build_response(
        self,
        *,
        answer: str,
        query: str,
        query_result: SPARQLExecutionResult,
        evidence: list[EvidenceRecord],
        trace_steps,
    ) -> dict[str, Any]:
        response = AnswerResponse(
            answer=answer,
            query=query,
            query_result=query_result.model_dump(),
            evidence=evidence,
            trace=self.trace_builder.build(trace_steps),
        )
        return response.model_dump()

    @staticmethod
    def _save_response(response: dict[str, Any]) -> None:
        DEFAULT_ANSWER_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_ANSWER_PATH.write_text(
            json.dumps(response, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_text(path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents.strip() + "\n", encoding="utf-8")

    @staticmethod
    def _relative_path(path: Path) -> str:
        try:
            return str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)
