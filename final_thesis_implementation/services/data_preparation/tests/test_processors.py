from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyarrow")

from thesis_data_prep.processors import _publish_tree


def test_publish_tree_creates_relative_symlink(tmp_path: Path) -> None:
    source = tmp_path / "raw" / "wiki"
    source.mkdir(parents=True)
    (source / "doc.txt").write_text("content", encoding="utf-8")
    output = tmp_path / "processed" / "wiki"

    _publish_tree(source, output, force=False)

    assert output.is_symlink()
    assert (output / "doc.txt").read_text(encoding="utf-8") == "content"
