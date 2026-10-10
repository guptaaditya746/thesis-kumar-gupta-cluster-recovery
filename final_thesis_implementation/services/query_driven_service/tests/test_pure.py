from query_driven.evaluation import list_em, list_f1, normalize_answer
from query_driven.pattern import parse_graph_pattern


def test_pattern_parser():
    value = parse_graph_pattern(
        'Entity types: [person, movie]##("relationship"<|>person<|>movie<|>directs)<|COMPLETE|>'
    )
    assert value["entity_types"] == ["person", "movie"]
    assert value["relationships"][0]["description"] == "directs"


def test_answer_normalization():
    assert normalize_answer("The Eiffel-Tower!") == "eiffel tower"


def test_list_metrics():
    assert list_em("Paris", ["Paris"]) == 1.0
    assert list_f1("Paris", ["Paris"]) == 1.0
