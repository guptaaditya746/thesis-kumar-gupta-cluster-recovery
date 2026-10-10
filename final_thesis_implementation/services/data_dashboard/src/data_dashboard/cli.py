from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from data_dashboard.catalog import build_catalog, catalog_exists, connect
from data_dashboard.config import DEFAULT_CONFIG, load_config

app = typer.Typer(no_args_is_help=True, help="Read-only thesis data observability dashboard.")
catalog_app = typer.Typer(no_args_is_help=True, help="Build or refresh the DuckDB catalog.")
app.add_typer(catalog_app, name="catalog")
console = Console()


def _config(value: Path | None):
    return load_config(value)


@app.command("config-check")
def config_check(
    config: Path | None = typer.Option(None, "--config", help="Path to dashboard YAML config."),
) -> None:
    """Validate configuration and print resolved paths."""
    cfg = _config(config)
    table = Table(title="Resolved dashboard configuration")
    table.add_column("Setting")
    table.add_column("Value")
    for key, value in (
        ("config", cfg.config_path),
        ("processed_root", cfg.processed_root),
        ("manifest_root", cfg.manifest_root),
        ("output_root", cfg.output_root),
        ("experiment_root", cfg.experiment_root),
        ("catalog", cfg.catalog.database),
    ):
        table.add_row(key, str(value))
    console.print(table)
    if not cfg.processed_root.exists():
        console.print("[yellow]Processed root does not exist yet. The dashboard can still be installed.[/yellow]")


@catalog_app.command("build")
def catalog_build(
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Create or replace catalog entries for configured processed data."""
    totals = build_catalog(_config(config))
    console.print(
        f"[green]Catalog complete:[/green] {totals['datasets']} artifacts, "
        f"{totals['files']} files, {totals['errors']} errors"
    )


@catalog_app.command("refresh")
def catalog_refresh(
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Alias for catalog build; retained for operational clarity."""
    catalog_build(config)


@app.command("status")
def status(
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Show cataloged artifacts and scan status."""
    cfg = _config(config)
    if not catalog_exists(cfg):
        console.print("[yellow]Catalog not found. Run: data-dashboard catalog build[/yellow]")
        raise typer.Exit(1)
    connection = connect(cfg, read_only=True)
    rows = connection.execute(
        """SELECT dataset_name, artifact_type, scanned_file_count, total_size_bytes,
                  record_count, scan_truncated, error
           FROM datasets ORDER BY artifact_type, dataset_name"""
    ).fetchall()
    connection.close()
    table = Table(title="Processed data catalog")
    for column in ("Dataset", "Type", "Files", "Bytes", "Records", "Truncated", "Error"):
        table.add_column(column)
    for row in rows:
        table.add_row(*["" if value is None else str(value) for value in row])
    console.print(table)


@app.command("validate")
def validate(
    config: Path | None = typer.Option(None, "--config"),
    output: Path | None = typer.Option(None, "--output", help="Optional JSON report path."),
) -> None:
    """Run catalog-level validation and optionally write a JSON report."""
    cfg = _config(config)
    if not catalog_exists(cfg):
        build_catalog(cfg)
    connection = connect(cfg, read_only=True)
    rows = connection.execute(
        """SELECT dataset_key, root_path, scanned_file_count, scan_truncated, error
           FROM datasets ORDER BY dataset_key"""
    ).fetchall()
    connection.close()
    report = []
    failed = False
    for dataset_key, root_path, count, truncated, error in rows:
        issues = []
        if not Path(root_path).exists():
            issues.append("root path does not exist")
        if count == 0:
            issues.append("no supported files cataloged")
        if truncated:
            issues.append("file scan reached configured limit")
        if error:
            issues.append(error)
        status_value = "error" if issues else "passed"
        failed = failed or bool(issues)
        report.append({"dataset_key": dataset_key, "status": status_value, "issues": issues})

    destination = output or (cfg.output_root / "validation_report.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    console.print(f"Validation report: {destination}")
    if failed:
        console.print("[yellow]Validation completed with warnings/errors.[/yellow]")
        raise typer.Exit(2)
    console.print("[green]All catalog-level checks passed.[/green]")


@app.command("serve")
def serve(
    config: Path | None = typer.Option(None, "--config"),
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
) -> None:
    """Launch the Streamlit dashboard."""
    cfg = _config(config)
    selected_host = host or cfg.server.host
    selected_port = port or cfg.server.port
    app_path = Path(__file__).resolve().parent / "app.py"
    env = os.environ.copy()
    env["DATA_DASHBOARD_CONFIG"] = str(cfg.config_path)
    command = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.address", selected_host,
        "--server.port", str(selected_port),
        "--global.developmentMode", "false",
    ]
    console.print(f"Starting dashboard on http://{selected_host}:{selected_port}")
    raise typer.Exit(subprocess.call(command, env=env))


if __name__ == "__main__":
    app()
