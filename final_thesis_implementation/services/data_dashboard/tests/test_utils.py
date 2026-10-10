from pathlib import Path

import pytest

from data_dashboard.utils import safe_resolve


def test_safe_resolve_accepts_child(tmp_path: Path):
    child = tmp_path / "data" / "file.txt"
    assert safe_resolve(child, [tmp_path]) == child.resolve(strict=False)


def test_safe_resolve_rejects_outside(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_resolve(Path("/etc/passwd"), [tmp_path])
