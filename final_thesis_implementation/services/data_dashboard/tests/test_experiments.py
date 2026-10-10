import json
from pathlib import Path

import pytest

from data_dashboard.experiments import (
    discover_experiment_runs,
    load_run_results,
    load_sample_artifacts,
)


def _run(root: Path) -> Path:
    run = root / "run-1"
    item = run / "items" / "sample-1"
    item.mkdir(parents=True)
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "benchmark": "bright",
                "status": "completed",
                "provenance": {"agent": {"model": "qwen-chat"}},
            }
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"primary_metric_name": "ndcg_at_10", "primary_metric_value": 0.75}),
        encoding="utf-8",
    )
    (run / "results.jsonl").write_text(
        json.dumps({"sample_id": "1", "item_dir": "items/sample-1"}) + "\n",
        encoding="utf-8",
    )
    (item / "input.json").write_text(json.dumps({"question": "q"}), encoding="utf-8")
    (item / "final.txt").write_text("answer", encoding="utf-8")
    return run


def test_experiment_discovery_and_sample_loading(tmp_path: Path) -> None:
    run = _run(tmp_path)
    records = discover_experiment_runs(tmp_path)
    assert records[0]["model"] == "qwen-chat"
    results = load_run_results(run, tmp_path)
    artifacts = load_sample_artifacts(run, results[0]["item_dir"], tmp_path)
    assert artifacts["input"]["question"] == "q"
    assert artifacts["final"] == "answer"


def test_sample_artifact_path_cannot_escape_run(tmp_path: Path) -> None:
    run = _run(tmp_path)
    with pytest.raises(ValueError):
        load_sample_artifacts(run, "../../outside", tmp_path)
