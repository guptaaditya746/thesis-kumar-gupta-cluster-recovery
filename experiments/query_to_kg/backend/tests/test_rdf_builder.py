from pathlib import Path

from rdflib import Literal
from rdflib.namespace import RDF

from backend.app.rdf import KG, RDFBuilder
from backend.tests.m4_fixtures import autograph_patch


def test_rdf_builder_materializes_autograph_patch(tmp_path):
    graph = RDFBuilder().build(autograph_patch())

    paper = KG.paper_autograph_r1
    method = KG.method_autograph_r1
    task = KG.task_knowledge_graph_construction
    evidence = KG.evidence_autograph_r1_abstract_0001
    evidence_text = (
        "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy "
        "learning problem, where the reward is derived from the graph's functional utility "
        "in a RAG pipeline."
    )

    assert (paper, RDF.type, KG.Paper) in graph
    assert (paper, KG.proposes, method) in graph
    assert (method, KG.addressesTask, task) in graph
    assert (evidence, KG.text, Literal(evidence_text)) in graph

    output_path = tmp_path / "graph.ttl"
    RDFBuilder().serialize(graph, output_path)

    assert output_path.exists()
    serialized = output_path.read_text(encoding="utf-8")
    assert "kg:paper_autograph_r1" in serialized
