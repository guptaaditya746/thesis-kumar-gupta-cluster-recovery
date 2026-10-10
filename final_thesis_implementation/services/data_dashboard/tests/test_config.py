from pathlib import Path

import yaml

from data_dashboard.config import load_config


def test_relative_paths_are_resolved(tmp_path: Path):
    service = tmp_path / "service"
    config_dir = service / "config"
    config_dir.mkdir(parents=True)
    path = config_dir / "dashboard.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "processed_root": "../../data/processed",
                "manifest_root": "../../data/manifests",
                "output_root": "../../outputs/data_dashboard",
                "catalog": {"database": "../../outputs/data_dashboard/catalog.duckdb"},
            }
        )
    )
    config = load_config(path)
    assert config.service_root == service.resolve()
    assert config.processed_root == (service / "../../data/processed").resolve()
    assert config.experiment_root == (service / "../../outputs/pi_bench/runs").resolve()
