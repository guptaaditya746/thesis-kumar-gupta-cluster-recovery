import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.extraction.kg_extractor import KGExtractor
from backend.app.extraction.query_understanding import QueryIntent
from backend.app.extraction.schemas import EdgeType, NodeType
from backend.app.retrieval.schemas import RetrievedChunk


@pytest.fixture
def mock_retrieved_chunks():
    return [
        RetrievedChunk(
            chunk_id="chunk_001",
            paper_id="test_paper",
            paper_title="Test Paper",
            section_id="sec_01",
            section_title="Introduction",
            raw_text="This paper proposes TestMethod, a new approach.",
            contextual_summary="A summary",
            score=0.9,
            retrieval_method="bm25",
            rank=1,
        )
    ]


@pytest.fixture
def mock_intent():
    return QueryIntent(
        intent_type="method_proposal",
        target_entities=["TestMethod"],
        needed_node_types=[NodeType.PAPER, NodeType.METHOD],
        needed_edge_types=[EdgeType.PROPOSES],
    )


def test_format_chunks(mock_retrieved_chunks):
    extractor = KGExtractor()
    formatted = extractor._format_chunks(mock_retrieved_chunks)
    assert "chunk_001" in formatted
    assert "Test Paper" in formatted
    assert "This paper proposes TestMethod, a new approach." in formatted


@patch("backend.app.extraction.kg_extractor.completion")
def test_extract_graph_patch_success(mock_completion, mock_retrieved_chunks, mock_intent):
    expected_patch = {
        "nodes": [
            {
                "id": "node_1",
                "type": "Paper",
                "label": "Test Paper",
                "properties": {},
                "provenance": {
                    "paper_id": "test_paper",
                    "chunk_id": "chunk_001",
                    "text_span": "This paper",
                },
            }
        ],
        "edges": [],
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(expected_patch)
    mock_completion.return_value = mock_response

    extractor = KGExtractor()
    result = extractor.extract_graph_patch(
        question="What does the paper propose?",
        intent=mock_intent,
        retrieved_chunks=mock_retrieved_chunks,
    )

    assert result == expected_patch
    mock_completion.assert_called_once()

    call_kwargs = mock_completion.call_args.kwargs
    prompt = call_kwargs["messages"][1]["content"]
    assert "What does the paper propose?" in prompt
    assert "method_proposal" in prompt
    assert "Paper, Method" in prompt
    assert "PROPOSES" in prompt


@patch("backend.app.extraction.kg_extractor.completion")
def test_extract_graph_patch_invalid_json(mock_completion, mock_retrieved_chunks, mock_intent):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is not JSON."
    mock_completion.return_value = mock_response

    extractor = KGExtractor()
    with pytest.raises(ValueError, match="Invalid or unparsable extraction output"):
        extractor.extract_graph_patch(
            question="What?",
            intent=mock_intent,
            retrieved_chunks=mock_retrieved_chunks,
        )


@patch("backend.app.extraction.kg_extractor.completion")
def test_extract_graph_patch_markdown_wrapper(mock_completion, mock_retrieved_chunks, mock_intent):
    expected_patch = {"nodes": [], "edges": []}
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = f"```json\n{json.dumps(expected_patch)}\n```"
    mock_completion.return_value = mock_response

    extractor = KGExtractor()
    result = extractor.extract_graph_patch(
        question="What?",
        intent=mock_intent,
        retrieved_chunks=mock_retrieved_chunks,
    )
    assert result == expected_patch


@patch("backend.app.extraction.kg_extractor.completion")
def test_extract_graph_patch_retries_truncated_json(mock_completion, mock_retrieved_chunks, mock_intent):
    first_response = MagicMock()
    first_response.choices = [MagicMock()]
    first_response.choices[0].message.content = '{"nodes": ['
    first_response.choices[0].finish_reason = "length"

    expected_patch = {"nodes": [], "edges": []}
    second_response = MagicMock()
    second_response.choices = [MagicMock()]
    second_response.choices[0].message.content = json.dumps(expected_patch)
    second_response.choices[0].finish_reason = "stop"

    mock_completion.side_effect = [first_response, second_response]

    extractor = KGExtractor()
    result = extractor.extract_graph_patch(
        question="What?",
        intent=mock_intent,
        retrieved_chunks=mock_retrieved_chunks,
    )

    assert result == expected_patch
    assert mock_completion.call_count == 2
    retry_system_prompt = mock_completion.call_args_list[1].kwargs["messages"][0]["content"]
    assert "no more than 12 nodes and 16 edges" in retry_system_prompt
