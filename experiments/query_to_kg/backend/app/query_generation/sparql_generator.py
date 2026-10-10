from typing import Any

from backend.app.extraction.schemas import EdgeType, GraphPatch
from backend.app.query_generation.prompts import SPARQL_GENERATION_PROMPT
from backend.app.query_generation.schema_context import SchemaContext, build_graph_summary

PREFIX_BLOCK = """PREFIX kg: <http://example.org/kg/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>"""


class SPARQLGenerator:
    """Deterministic SPARQL generation for milestone 4 demo questions."""

    def build_prompt(
        self,
        question: str,
        schema_context: SchemaContext,
        graph_patch: GraphPatch | dict[str, Any],
    ) -> str:
        return SPARQL_GENERATION_PROMPT.format(
            question=question,
            schema_context=schema_context.render(),
            graph_summary=build_graph_summary(graph_patch),
        )

    def generate(
        self,
        question: str,
        schema_context: SchemaContext,
        graph_patch: GraphPatch | dict[str, Any],
    ) -> str:
        patch = graph_patch if isinstance(graph_patch, GraphPatch) else GraphPatch(**graph_patch)
        lowered_question = question.lower()

        if self._is_method_question(lowered_question, patch):
            return self._method_query()
        if self._is_validation_question(lowered_question, patch):
            return self._validation_query()
        if self._is_claim_question(lowered_question, patch):
            return self._claim_query()
        return self._fallback_query(patch)

    def repair(self, query: str, error: str | None = None) -> str:
        cleaned = query.strip()
        if cleaned.startswith("```sparql"):
            cleaned = cleaned[len("```sparql"):]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        if "SELECT" in cleaned.upper() and not cleaned.upper().startswith("PREFIX"):
            cleaned = f"{PREFIX_BLOCK}\n\n{cleaned}"
        if "LIMIT" not in cleaned.upper():
            cleaned = f"{cleaned}\nLIMIT 5"
        return cleaned

    @staticmethod
    def _is_method_question(question: str, patch: GraphPatch) -> bool:
        edge_types = {edge.type for edge in patch.edges}
        has_paper_method_signal = EdgeType.PROPOSES in edge_types or EdgeType.FROM_PAPER in edge_types
        return (
            has_paper_method_signal
            and EdgeType.ADDRESSES_TASK in edge_types
            and (
                "propose" in question
                or "method" in question
                or "reinforcement" in question
                or "knowledge graph construction" in question
            )
        )

    @staticmethod
    def _is_claim_question(question: str, patch: GraphPatch) -> bool:
        edge_types = {edge.type for edge in patch.edges}
        return EdgeType.MAKES_CLAIM in edge_types and (
            "graph" in question
            or "retrieval" in question
            or "relationship" in question
        )

    @staticmethod
    def _is_validation_question(question: str, patch: GraphPatch) -> bool:
        edge_types = {edge.type for edge in patch.edges}
        return (EdgeType.DESCRIBES in edge_types or EdgeType.MAKES_CLAIM in edge_types) and (
            "validation" in question
            or "schema" in question
            or "runtime" in question
            or "graph quer" in question
        )

    @staticmethod
    def _method_query() -> str:
        return f"""{PREFIX_BLOCK}

SELECT ?paperTitle ?methodName ?taskName ?evidenceText
WHERE {{
  ?paper rdf:type kg:Paper ;
         kg:title ?paperTitle ;
         kg:proposes ?method .

  ?method rdf:type kg:Method ;
          kg:name ?methodName ;
          kg:addressesTask ?task ;
          kg:supportedBy ?evidence .
  OPTIONAL {{ ?method kg:description ?methodDescription . }}

  ?task rdf:type kg:Task ;
        kg:name ?taskName .

  ?evidence rdf:type kg:Evidence ;
            kg:text ?evidenceText .

  FILTER(
    CONTAINS(LCASE(?taskName), "knowledge graph construction")
    || CONTAINS(LCASE(?taskName), "kg construction")
    || CONTAINS(LCASE(?evidenceText), "knowledge graph construction")
    || CONTAINS(LCASE(?evidenceText), "kg construction")
    || (BOUND(?methodDescription) && CONTAINS(LCASE(?methodDescription), "knowledge graph construction"))
    || (BOUND(?methodDescription) && CONTAINS(LCASE(?methodDescription), "kg construction"))
  )
  FILTER(
    CONTAINS(LCASE(?paperTitle), "reinforcement learning")
    || (BOUND(?methodDescription) && CONTAINS(LCASE(?methodDescription), "reinforcement learning"))
    || CONTAINS(LCASE(?evidenceText), "reinforcement learning")
    || CONTAINS(LCASE(?evidenceText), "policy learning")
  )
}}
LIMIT 5"""

    @staticmethod
    def _claim_query() -> str:
        return f"""{PREFIX_BLOCK}

SELECT ?paperTitle ?claimText ?evidenceText
WHERE {{
  ?paper rdf:type kg:Paper ;
         kg:title ?paperTitle ;
         kg:makesClaim ?claim .

  ?claim rdf:type kg:Claim ;
         kg:text ?claimText ;
         kg:supportedBy ?evidence .

  ?evidence rdf:type kg:Evidence ;
            kg:text ?evidenceText .

  FILTER(CONTAINS(LCASE(?claimText), "graph"))
  FILTER(CONTAINS(LCASE(?claimText), "retrieval") || CONTAINS(LCASE(?evidenceText), "retrieval"))
}}
LIMIT 5"""

    @staticmethod
    def _validation_query() -> str:
        return f"""{PREFIX_BLOCK}

SELECT ?paperTitle ?claimText ?evidenceText
WHERE {{
  ?paper rdf:type kg:Paper ;
         kg:title ?paperTitle ;
         kg:describes ?claim .

  ?claim rdf:type kg:Claim ;
         kg:text ?claimText ;
         kg:supportedBy ?evidence .

  ?evidence rdf:type kg:Evidence ;
            kg:text ?evidenceText .

  FILTER(
    CONTAINS(LCASE(?claimText), "validation")
    || CONTAINS(LCASE(?evidenceText), "schema")
    || CONTAINS(LCASE(?evidenceText), "runtime")
    || CONTAINS(LCASE(?evidenceText), "logical")
  )
}}
LIMIT 5"""

    @staticmethod
    def _fallback_query(patch: GraphPatch) -> str:
        edge_types = {edge.type for edge in patch.edges}
        if EdgeType.PROPOSES in edge_types:
            return SPARQLGenerator._method_query()
        if EdgeType.DESCRIBES in edge_types:
            return SPARQLGenerator._validation_query()
        return SPARQLGenerator._claim_query()


def generate_sparql(
    question: str,
    schema_context: SchemaContext,
    graph_patch: GraphPatch | dict[str, Any],
) -> str:
    return SPARQLGenerator().generate(question, schema_context, graph_patch)
