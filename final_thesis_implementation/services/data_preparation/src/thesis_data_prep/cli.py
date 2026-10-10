from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from huggingface_hub import get_token
from rich.console import Console
from rich.table import Table

from thesis_data_prep.manifest import write_dataset_manifest
from thesis_data_prep.service import (
    assert_large_resources_allowed,
    prepare_datasets,
    resolve_dataset_names,
    resources_for_datasets,
)
from thesis_data_prep.settings import ResolvedConfig, load_config
from thesis_data_prep.utils import ensure_data_layout, human_bytes
from thesis_data_prep.validation import validate_resource

app = typer.Typer(
    name="data-prep",
    help="Download, preprocess, validate, and publish thesis benchmark data and corpora.",
    no_args_is_help=True,
)
console = Console()


@dataclass
class AppContext:
    settings: ResolvedConfig


@app.callback()
def callback(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option("--config", envvar="DATA_PREP_CONFIG", help="Path to datasets.yaml."),
    ] = None,
    data_root: Annotated[
        Path | None,
        typer.Option("--data-root", envvar="DATA_PREP_DATA_ROOT", help="Override data root."),
    ] = None,
) -> None:
    ctx.obj = AppContext(load_config(config, data_root))


def _settings(ctx: typer.Context) -> ResolvedConfig:
    return ctx.obj.settings


@app.command("init")
def init_layout(ctx: typer.Context) -> None:
    """Create the isolated data directory layout without deleting anything."""
    settings = _settings(ctx)
    ensure_data_layout(settings.data_root)
    readme = settings.data_root / "README.data-layout.md"
    if not readme.exists():
        readme.write_text(
            "# Managed data directory\n\n"
            "This directory is managed by the thesis data-preparation service.\n\n"
            "- `raw/`: immutable upstream downloads\n"
            "- `interim/`: disposable temporary artifacts\n"
            "- `processed/benchmarks/`: benchmark files consumed by experiments\n"
            "- `processed/corpora/`: searchable corpora consumed by agents\n"
            "- `manifests/`: provenance and validation metadata\n"
            "- `checksums/`: optional checksums\n"
            "- `logs/`: pipeline logs\n",
            encoding="utf-8",
        )
    console.print(f"[green]initialized[/green] {settings.data_root}")


@app.command("catalog")
def catalog(ctx: typer.Context) -> None:
    """List configured datasets and their benchmark/corpus resources."""
    settings = _settings(ctx)
    table = Table(title="Configured datasets")
    table.add_column("Dataset")
    table.add_column("Benchmark resource")
    table.add_column("Corpus resource")
    table.add_column("Large")
    table.add_column("Description")
    for name, dataset in settings.config.datasets.items():
        large = settings.resource(dataset.benchmark).large or settings.resource(dataset.corpus).large
        table.add_row(name, dataset.benchmark, dataset.corpus, "yes" if large else "no", dataset.description)
    console.print(table)
    if settings.config.groups:
        group_table = Table(title="Dataset groups")
        group_table.add_column("Group")
        group_table.add_column("Members")
        for name, members in settings.config.groups.items():
            group_table.add_row(name, ", ".join(members))
        console.print(group_table)


@app.command("doctor")
def doctor(ctx: typer.Context) -> None:
    """Check configuration, authentication, write access, and free disk space."""
    settings = _settings(ctx)
    ensure_data_layout(settings.data_root)
    usage = shutil.disk_usage(settings.data_root)
    checks = Table(title="Data preparation doctor")
    checks.add_column("Check")
    checks.add_column("Result")
    checks.add_row("Config", str(settings.config_path))
    checks.add_row("Workspace root", str(settings.workspace_root))
    checks.add_row("Data root", str(settings.data_root))
    checks.add_row("Data root writable", "yes" if settings.data_root.exists() else "no")
    checks.add_row("Hugging Face token", "available" if get_token() else "not found")
    checks.add_row("Disk free", human_bytes(usage.free))
    checks.add_row("Disk total", human_bytes(usage.total))
    console.print(checks)
    if not get_token():
        console.print(
            "[yellow]Authentication may be required.[/yellow] Run `hf auth login` before downloads."
        )


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Show whether raw and processed resources currently exist."""
    settings = _settings(ctx)
    table = Table(title="Resource status")
    table.add_column("Resource")
    table.add_column("Kind")
    table.add_column("Raw source")
    table.add_column("Processed output")
    table.add_column("Valid")
    for name, resource in settings.config.resources.items():
        source = settings.resource_source(name)
        output = settings.resource_output(name)
        result = validate_resource(settings, name) if output.exists() or output.is_symlink() else None
        table.add_row(
            name,
            resource.kind,
            "yes" if source.exists() else "no",
            "yes" if output.exists() or output.is_symlink() else "no",
            "yes" if result and result.ok else "no",
        )
    console.print(table)


@app.command("prepare")
def prepare(
    ctx: typer.Context,
    datasets: Annotated[
        list[str],
        typer.Argument(help="Dataset names, aliases, or `all`."),
    ],
    download: Annotated[
        bool,
        typer.Option("--download/--no-download", help="Download missing upstream resources first."),
    ] = True,
    include_large: Annotated[
        bool,
        typer.Option(help="Allow resources marked large, including the Wikipedia corpus."),
    ] = False,
    force_download: Annotated[
        bool,
        typer.Option(help="Ask Hugging Face to re-download selected files."),
    ] = False,
    force_process: Annotated[
        bool,
        typer.Option(help="Delete and rebuild processed outputs for selected resources."),
    ] = False,
) -> None:
    """Download, process, validate, and manifest one or more datasets."""
    settings = _settings(ctx)
    ensure_data_layout(settings.data_root)
    results = prepare_datasets(
        settings,
        datasets,
        download=download,
        force_download=force_download,
        force_process=force_process,
        include_large=include_large,
    )
    for result in results:
        console.print(f"[green]valid[/green] {result.resource}")


@app.command("validate")
def validate(
    ctx: typer.Context,
    datasets: Annotated[list[str], typer.Argument(help="Dataset names, aliases, or `all`.")],
    include_large: Annotated[
        bool,
        typer.Option(help="Allow validation of resources marked large."),
    ] = False,
) -> None:
    """Validate already prepared outputs without downloading or processing."""
    settings = _settings(ctx)
    canonical = resolve_dataset_names(settings, datasets)
    resources = resources_for_datasets(settings, canonical)
    assert_large_resources_allowed(settings, resources, include_large=include_large)
    failed = False
    for resource_name in resources:
        result = validate_resource(settings, resource_name)
        if result.ok:
            console.print(f"[green]valid[/green] {resource_name}")
        else:
            failed = True
            console.print(f"[red]invalid[/red] {resource_name}: {'; '.join(result.errors)}")
    if failed:
        raise typer.Exit(code=1)


@app.command("manifest")
def manifest(
    ctx: typer.Context,
    datasets: Annotated[list[str], typer.Argument(help="Dataset names, aliases, or `all`.")],
) -> None:
    """Regenerate provenance manifests for prepared datasets."""
    settings = _settings(ctx)
    for dataset_name in resolve_dataset_names(settings, datasets):
        path = write_dataset_manifest(settings, dataset_name)
        console.print(f"[green]wrote[/green] {path}")


if __name__ == "__main__":
    app()
