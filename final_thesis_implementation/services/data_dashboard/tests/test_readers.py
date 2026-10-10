from pathlib import Path

from data_dashboard.readers import preview_file, record_count


def test_jsonl_preview_and_count(tmp_path: Path):
    path = tmp_path / "sample.jsonl"
    path.write_text('{"id": 1, "text": "alpha"}\n{"id": 2, "text": "beta"}\n')
    frame = preview_file(path, limit=1)
    assert len(frame) == 1
    assert frame.iloc[0]["id"] == 1
    count, exact = record_count(path, exact_count_max_bytes=1024)
    assert count == 2
    assert exact is True
