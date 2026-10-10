"""RDF materialization and SPARQL execution helpers."""

from .namespace import KG, RDF_NS
from .rdf_builder import RDFBuilder, build_rdf_graph
from .sparql_executor import SPARQLExecutionResult, SPARQLExecutor, execute_sparql

__all__ = [
    "KG",
    "RDF_NS",
    "RDFBuilder",
    "SPARQLExecutionResult",
    "SPARQLExecutor",
    "build_rdf_graph",
    "execute_sparql",
]
