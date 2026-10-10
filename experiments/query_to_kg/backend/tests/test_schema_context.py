from backend.app.query_generation.schema_context import SchemaContextBuilder
from backend.app.rdf.rdf_schema import CLASS_NAMES, PREDICATE_NAMES
from backend.tests.m4_fixtures import autograph_patch


def test_schema_context_includes_allowed_vocab_and_observed_terms():
    schema_context = SchemaContextBuilder().build(autograph_patch())

    assert schema_context.prefixes == {
        "kg": "http://example.org/kg/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }
    assert schema_context.classes == [f"kg:{name}" for name in CLASS_NAMES]
    assert schema_context.predicates == [f"kg:{name}" for name in PREDICATE_NAMES]
    assert schema_context.observed_classes == ["Paper", "Method", "Task", "Evidence"]
    assert schema_context.observed_predicates == ["proposes", "addressesTask", "supportedBy"]
