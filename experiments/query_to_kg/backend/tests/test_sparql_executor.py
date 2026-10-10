from backend.app.query_generation.schema_context import SchemaContextBuilder
from backend.app.query_generation.sparql_generator import SPARQLGenerator
from backend.app.rdf.rdf_builder import RDFBuilder
from backend.app.rdf.sparql_executor import SPARQLExecutor
from backend.tests.m4_fixtures import QUESTION, autograph_patch


def test_sparql_executor_returns_autograph_result():
    patch = autograph_patch()
    graph = RDFBuilder().build(patch)
    schema_context = SchemaContextBuilder().build(patch)
    query = SPARQLGenerator().generate(QUESTION, schema_context, patch)

    result = SPARQLExecutor().execute(graph, query)

    assert result.status == "success"
    assert result.row_count == 1
    assert result.columns == ["paperTitle", "methodName", "taskName", "evidenceText"]
    assert result.rows[0]["paperTitle"] == (
        "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction"
    )
    assert "policy learning problem" in result.rows[0]["evidenceText"]


def test_sparql_executor_reports_query_error():
    graph = RDFBuilder().build(autograph_patch())

    result = SPARQLExecutor().execute(graph, "SELECT WHERE {")

    assert result.status == "error"
    assert result.row_count == 0
    assert "SPARQL" in result.error
