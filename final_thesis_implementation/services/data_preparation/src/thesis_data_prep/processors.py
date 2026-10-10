from __future__ import annotations

from pathlib import Path

from rich.console import Console

from thesis_data_prep.settings import ResolvedConfig
from thesis_data_prep.utils import atomic_copy, relative_symlink, remove_path

console = Console()


def _publish_file(source: Path, output: Path, *, force: bool) -> int:
    if not source.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source}")
    if output.exists() and not force:
        console.print(f"[yellow]skip[/yellow] existing published file: {output}")
        return 1
    atomic_copy(source, output)
    console.print(f"[green]published[/green] {source} -> {output}")
    return 1


def _publish_tree(source: Path, output: Path, *, force: bool) -> int:
    if not source.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source}")
    if output.is_symlink() and output.resolve() == source.resolve() and not force:
        console.print(f"[yellow]skip[/yellow] existing corpus alias: {output}")
        return 1
    if output.exists() or output.is_symlink():
        if not force:
            raise FileExistsError(f"Output already exists: {output}. Use --force to replace it.")
        remove_path(output)
    relative_symlink(source, output)
    console.print(f"[green]linked[/green] {output} -> {source}")
    return 1


def process_resource(settings: ResolvedConfig, resource_name: str, *, force: bool = False) -> int:
    resource = settings.resource(resource_name)
    source = settings.resource_source(resource_name)
    output = settings.resource_output(resource_name)
    options = resource.options

    if resource.processor == "bcplus_qa":
        from thesis_data_prep import bcplus

        return bcplus.extract_qa(
            source,
            output,
            decrypt=bool(options.get("decrypt", True)),
            force=force,
        )
    if resource.processor == "browsecomp_docs":
        from thesis_data_prep import bcplus

        return bcplus.export_documents(source, output, force=force)
    if resource.processor == "bright_docs":
        from thesis_data_prep import bright

        return bright.export_documents(source, output, force=force)
    if resource.processor == "publish_file":
        return _publish_file(source, output, force=force)
    if resource.processor == "publish_tree":
        return _publish_tree(source, output, force=force)
    raise ValueError(f"Unsupported processor: {resource.processor}")
