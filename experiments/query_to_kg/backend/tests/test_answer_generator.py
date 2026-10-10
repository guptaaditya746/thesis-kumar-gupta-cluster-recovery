from backend.app.answering.answer_generator import AnswerGenerator
from backend.app.answering.schemas import EvidenceRecord

QUESTION = "Which paper proposes a reinforcement-learning approach for knowledge graph construction?"
QUERY = "SELECT ?paperTitle WHERE { ?paper ?p ?o } LIMIT 5"


def test_answer_generator_builds_grounded_answer():
    evidence = [
        EvidenceRecord(
            paper_id="autograph_r1",
            paper_title="AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
            section_title="Abstract",
            chunk_id="autograph_r1_abstract_0001",
            text_span=(
                "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy "
                "learning problem, where the reward is derived from the graph's functional utility "
                "in a RAG pipeline."
            ),
        )
    ]
    query_result = {
        "status": "success",
        "row_count": 1,
        "rows": [
            {
                "paperTitle": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                "methodName": "AutoGraph-R1",
                "taskName": "Knowledge graph construction",
                "evidenceText": (
                    "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy "
                    "learning problem, where the reward is derived from the graph's functional utility "
                    "in a RAG pipeline."
                ),
            }
        ],
    }

    answer = AnswerGenerator().generate(QUESTION, QUERY, query_result, evidence)

    assert "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction" in answer
    assert "policy learning problem" in answer


def test_answer_generator_handles_empty_rows_honestly():
    answer = AnswerGenerator().generate(
        QUESTION,
        QUERY,
        {"status": "success", "row_count": 0, "rows": []},
        [],
    )

    assert "did not contain enough evidence" in answer


def test_answer_generator_handles_validation_error():
    answer = AnswerGenerator().generate(
        QUESTION,
        QUERY,
        {"status": "validation_error", "row_count": 0, "rows": []},
        [],
    )

    assert "SPARQL query was invalid" in answer
