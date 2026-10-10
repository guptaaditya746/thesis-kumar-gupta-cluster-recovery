from __future__ import annotations

from collections.abc import Iterable

from rich.console import Console

from thesis_data_prep.download import download_resources
from thesis_data_prep.manifest import write_dataset_manifest
from thesis_data_prep.processors import process_resource
from thesis_data_prep.settings import ResolvedConfig
from thesis_data_prep.utils import unique_preserving_order
from thesis_data_prep.validation import ValidationResult, validate_resource

console = Console()


def resolve_dataset_names(settings: ResolvedConfig, names: Iterable[str]) -> list[str]:
    raw = list(names)
    if not raw:
        return list(settings.config.datasets)

    canonical: list[str] = []
    for name in raw:
        normalized = name.strip().lower().replace("-", "_")
        if normalized == "all":
            canonical.extend(settings.config.datasets)
            continue
        if normalized in settings.config.groups:
            for group_member in settings.config.groups[normalized]:
                canonical.append(settings.dataset(group_member)[0])
            continue
        canonical.append(settings.dataset(name)[0])
    return unique_preserving_order(canonical)


def resources_for_datasets(settings: ResolvedConfig, dataset_names: Iterable[str]) -> list[str]:
    resources: list[str] = []
    for name in dataset_names:
        _, dataset = settings.dataset(name)
        resources.extend([dataset.benchmark, dataset.corpus])
    return unique_preserving_order(resources)


def assert_large_resources_allowed(
    settings: ResolvedConfig, resources: Iterable[str], *, include_large: bool
) -> None:
    blocked = [name for name in resources if settings.resource(name).large]
    if blocked and not include_large:
        raise RuntimeError(
            "Large resources were selected: "
            + ", ".join(blocked)
            + ". Re-run with --include-large after checking storage quota."
        )


def prepare_datasets(
    settings: ResolvedConfig,
    dataset_names: Iterable[str],
    *,
    download: bool,
    force_download: bool,
    force_process: bool,
    include_large: bool,
) -> list[ValidationResult]:
    canonical = resolve_dataset_names(settings, dataset_names)
    resources = resources_for_datasets(settings, canonical)
    assert_large_resources_allowed(settings, resources, include_large=include_large)

    if download:
        download_resources(settings, resources, force=force_download)

    for resource_name in resources:
        source = settings.resource_source(resource_name)
        if not source.exists():
            raise FileNotFoundError(
                f"Missing raw source for {resource_name}: {source}. Run with --download."
            )
        process_resource(settings, resource_name, force=force_process)

    results = [validate_resource(settings, resource_name) for resource_name in resources]
    failed = [result for result in results if not result.ok]
    if failed:
        messages = [f"{result.resource}: {', '.join(result.errors)}" for result in failed]
        raise RuntimeError("Validation failed after preparation:\n" + "\n".join(messages))

    for dataset_name in canonical:
        path = write_dataset_manifest(settings, dataset_name)
        console.print(f"[green]manifest[/green] {path}")
    return results
