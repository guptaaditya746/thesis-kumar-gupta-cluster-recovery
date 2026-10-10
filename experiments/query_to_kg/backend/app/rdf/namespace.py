from rdflib import Graph, Namespace

KG = Namespace("http://example.org/kg/")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


def bind_namespaces(graph: Graph) -> Graph:
    """Bind the RDF namespaces used across the milestone 4 pipeline."""
    graph.bind("kg", KG)
    graph.bind("rdf", RDF_NS)
    return graph
