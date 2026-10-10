import re

from pydantic import BaseModel, Field
from rdflib.plugins.sparql.parser import parseQuery

from backend.app.rdf.namespace import KG, RDF_NS
from backend.app.rdf.rdf_schema import CLASS_NAMES, PREDICATE_NAMES

FORBIDDEN = [
    "INSERT",
    "DELETE",
    "DROP",
    "CLEAR",
    "LOAD",
    "CREATE",
    "COPY",
    "MOVE",
    "ADD",
    "WITH",
    "USING",
    "SERVICE",
]

ALLOWED_KG_TERMS = set(CLASS_NAMES) | set(PREDICATE_NAMES)
ALLOWED_PREFIX_IRIS = {str(KG), str(RDF_NS)}


class SPARQLValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SPARQLValidator:
    """Validate generated SPARQL queries before execution."""

    def validate(self, query: str) -> SPARQLValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        cleaned = query.strip()
        upper = cleaned.upper()

        if not cleaned:
            errors.append("Query is empty.")
        if cleaned and not (upper.startswith("PREFIX") or upper.startswith("SELECT")):
            errors.append("Query must start with PREFIX or SELECT.")
        if "SELECT" not in upper:
            errors.append("Only SELECT queries are allowed.")
        if re.search(r"\b(ASK|CONSTRUCT|DESCRIBE)\b", upper):
            errors.append("Only SELECT queries are allowed.")

        for keyword in FORBIDDEN:
            if re.search(rf"\b{keyword}\b", upper):
                errors.append(f"Forbidden keyword detected: {keyword}.")

        if cleaned.count("{") != cleaned.count("}"):
            errors.append("Query has unbalanced braces.")
        if re.search(r"\bSERVICE\b", upper):
            errors.append("SERVICE clauses are not allowed.")

        self._validate_remote_iris(cleaned, errors)
        self._validate_kg_terms(cleaned, errors)

        if "LIMIT" not in upper and not self._is_naturally_narrow(cleaned):
            warnings.append("Query has no LIMIT and does not look naturally narrow.")

        try:
            parseQuery(cleaned)
        except Exception as exc:
            errors.append(f"SPARQL parse error: {exc}")

        return SPARQLValidationResult(valid=not errors, errors=errors, warnings=warnings)

    @staticmethod
    def _validate_remote_iris(query: str, errors: list[str]) -> None:
        body_lines = [
            line
            for line in query.splitlines()
            if not line.lstrip().upper().startswith("PREFIX ")
        ]
        body_text = "\n".join(body_lines)
        for iri in re.findall(r"<([^>]+)>", body_text):
            if iri not in ALLOWED_PREFIX_IRIS:
                errors.append(f"Remote or inline IRI is not allowed in query body: <{iri}>.")
        if re.search(r"https?://", body_text):
            errors.append("Remote URLs are not allowed in query body.")

    @staticmethod
    def _validate_kg_terms(query: str, errors: list[str]) -> None:
        used_terms = set(re.findall(r"\bkg:([A-Za-z][A-Za-z0-9_]*)\b", query))
        unknown_terms = sorted(used_terms - ALLOWED_KG_TERMS)
        for term in unknown_terms:
            errors.append(f"Unknown kg: term used in query: kg:{term}.")

    @staticmethod
    def _is_naturally_narrow(query: str) -> bool:
        triple_line_count = sum(
            1
            for line in query.splitlines()
            if "kg:" in line and not line.lstrip().upper().startswith("PREFIX ")
        )
        has_filter = "FILTER" in query.upper()
        return has_filter and triple_line_count <= 8


def validate_sparql(query: str) -> SPARQLValidationResult:
    return SPARQLValidator().validate(query)
