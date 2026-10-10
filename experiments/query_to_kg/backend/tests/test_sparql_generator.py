import re

from backend.app.query_generation.schema_context import SchemaContextBuilder
from backend.app.query_generation.sparql_generator import SPARQLGenerator
from backend.tests.m4_fixtures import QUESTION, autograph_patch


FORBIDDEN_QUERY_TYPES = ("ASK", "CONSTRUCT", "DESCRIBE")


def test_sparql_generator_returns_select_only_query():
    patch = autograph_patch()
    schema_context = SchemaContextBuilder().build(patch)

    query = SPARQLGenerator().generate(QUESTION, schema_context, patch)
    upper = query.upper()

    assert query.lstrip().startswith("PREFIX kg:")
    assert "SELECT" in upper
    for keyword in FORBIDDEN_QUERY_TYPES:
        assert re.search(rf"\\b{keyword}\\b", upper) is None
