from rdflib import Literal

from backend.app.query_generation.schema_context import SchemaContextBuilder
from backend.app.query_generation.sparql_generator import SPARQLGenerator
from backend.app.rdf import KG, RDFBuilder
from backend.app.rdf.sparql_executor import SPARQLExecutor

QUESTION = "What method does AutoGraph-R1 propose for knowledge graph construction?"


def m3_method_patch_without_evidence_node() -> dict:
    return {
        "nodes": [
            {
                "id": "paper:autograph_r1",
                "type": "Paper",
                "label": "AutoGraph-R1",
                "properties": {"title": "AutoGraph-R1"},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_preamble_0001",
                    "text_span": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "paper_title": "AutoGraph-R1",
                    "section_title": "Preamble",
                },
            },
            {
                "id": "method:autograph_r1_rl_framework",
                "type": "Method",
                "label": "AutoGraph-R1 RL Framework",
                "properties": {"name": "AutoGraph-R1 RL Framework"},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL).",
                    "paper_title": "AutoGraph-R1",
                    "section_title": "Abstract",
                },
            },
            {
                "id": "task:downstream_qa_task",
                "type": "Task",
                "label": "Downstream QA Task",
                "properties": {"name": "Downstream QA Task"},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "Building effective knowledge graphs (KGs) for Retrieval-Augmented Generation (RAG) is pivotal for advancing question answering (QA) systems.",
                    "paper_title": "AutoGraph-R1",
                    "section_title": "Abstract",
                },
            },
        ],
        "edges": [
            {
                "source": "method:autograph_r1_rl_framework",
                "target": "task:downstream_qa_task",
                "type": "ADDRESSES_TASK",
                "properties": {},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy learning problem.",
                    "paper_title": "AutoGraph-R1",
                    "section_title": "Abstract",
                },
            },
            {
                "source": "method:autograph_r1_rl_framework",
                "target": "paper:autograph_r1",
                "type": "FROM_PAPER",
                "properties": {},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL).",
                    "paper_title": "AutoGraph-R1",
                    "section_title": "Abstract",
                },
            },
        ],
    }


def test_rdf_builder_derives_queryable_method_edges_from_m3_shape():
    graph = RDFBuilder().build(m3_method_patch_without_evidence_node())

    paper = KG.paper_autograph_r1
    method = KG.method_autograph_r1_rl_framework
    derived_evidence = KG.evidence_autograph_r1_abstract_0001_from_paper_method_autograph_r1_rl_framework_paper_autograph_r1

    assert (paper, KG.proposes, method) in graph
    assert (method, KG.supportedBy, derived_evidence) in graph
    assert (
        derived_evidence,
        KG.text,
        Literal(
            "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL)."
        ),
    ) in graph


def test_method_sparql_answers_m3_method_patch_shape():
    patch = m3_method_patch_without_evidence_node()
    graph = RDFBuilder().build(patch)
    schema_context = SchemaContextBuilder().build(patch)
    query = SPARQLGenerator().generate(QUESTION, schema_context, patch)

    result = SPARQLExecutor().execute(graph, query)

    assert result.status == "success"
    assert result.row_count >= 1
    assert result.rows[0]["methodName"] == "AutoGraph-R1 RL Framework"
    assert "Reinforcement Learning" in result.rows[0]["evidenceText"]
