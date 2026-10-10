from backend.app.query_generation.sparql_validator import SPARQLValidator

VALID_QUERY = """PREFIX kg: <http://example.org/kg/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?paperTitle ?methodName ?taskName ?evidenceText
WHERE {
  ?paper rdf:type kg:Paper ;
         kg:title ?paperTitle ;
         kg:proposes ?method .
  ?method rdf:type kg:Method ;
          kg:name ?methodName ;
          kg:addressesTask ?task ;
          kg:supportedBy ?evidence .
  ?task rdf:type kg:Task ;
        kg:name ?taskName .
  ?evidence rdf:type kg:Evidence ;
            kg:text ?evidenceText .
  FILTER(CONTAINS(LCASE(?evidenceText), "reinforcement learning"))
}
LIMIT 5"""


def test_sparql_validator_accepts_select_query():
    result = SPARQLValidator().validate(VALID_QUERY)

    assert result.valid is True
    assert result.errors == []


def test_sparql_validator_rejects_destructive_query():
    query = "DELETE WHERE { ?s ?p ?o }"
    result = SPARQLValidator().validate(query)

    assert result.valid is False
    assert any("DELETE" in error for error in result.errors)


def test_sparql_validator_rejects_unknown_predicate():
    query = """PREFIX kg: <http://example.org/kg/>
SELECT ?paper WHERE {
  ?paper kg:notAllowed ?value .
}
LIMIT 5"""
    result = SPARQLValidator().validate(query)

    assert result.valid is False
    assert any("kg:notAllowed" in error for error in result.errors)
