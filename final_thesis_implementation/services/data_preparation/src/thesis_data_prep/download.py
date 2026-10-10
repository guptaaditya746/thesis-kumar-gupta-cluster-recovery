from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from time import sleep
from typing import Iterable

from huggingface_hub import HfApi, snapshot_download
from rich.console import Console
from thesis_data_prep.settings import ResolvedConfig
from thesis_data_prep.utils import atomic_write_json, ensure_data_layout, utc_now

console = Console()


def _snapshot_download(**kwargs: object) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return snapshot_download(**kwargs)
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            sleep(2**attempt)
    assert last_error is not None
    raise last_error


def _resolve_revision(repo_id: str, repo_type: str, revision: str | None) -> str | None:
    try:
        info = HfApi().repo_info(repo_id=repo_id, repo_type=repo_type, revision=revision)
        return info.sha
    except Exception:
        return revision


def download_resources(
    settings: ResolvedConfig,
    resource_names: Iterable[str],
    *,
    force: bool = False,
) -> None:
    ensure_data_layout(settings.data_root)
    grouped: dict[str, list[str]] = defaultdict(list)
    for resource_name in resource_names:
        resource = settings.resource(resource_name)
        grouped[resource.repository].append(resource_name)

    for repository_name, names in grouped.items():
        repository = settings.repository(repository_name)
        destination = settings.repository_root(repository_name)
        destination.mkdir(parents=True, exist_ok=True)
        patterns: list[str] = []
        for name in names:
            patterns.extend(settings.resource(name).allow_patterns)
        patterns = sorted(set(patterns))

        console.print(
            f"[bold cyan]Downloading[/bold cyan] {repository.repo_id} "
            f"for {', '.join(sorted(names))}"
        )
        result_path = _snapshot_download(
            repo_id=repository.repo_id,
            repo_type=repository.repo_type,
            revision=repository.revision,
            local_dir=str(destination),
            allow_patterns=patterns,
            force_download=force,
        )
        resolved_revision = _resolve_revision(
            repository.repo_id, repository.repo_type, repository.revision
        )

        for resource_name in names:
            source = settings.resource_source(resource_name)
            if not source.exists():
                raise FileNotFoundError(
                    f"Download finished, but resource source is missing: {source}. "
                    "The configured allow_patterns or source path may be stale."
                )
            marker = settings.data_root / "manifests" / "downloads" / f"{resource_name}.json"
            atomic_write_json(
                marker,
                {
                    "resource": resource_name,
                    "repository": repository.repo_id,
                    "repository_type": repository.repo_type,
                    "requested_revision": repository.revision,
                    "resolved_revision": resolved_revision,
                    "allow_patterns": settings.resource(resource_name).allow_patterns,
                    "source": str(source),
                    "snapshot_result": str(Path(result_path).resolve()),
                    "downloaded_at": utc_now(),
                },
            )
            console.print(f"  [green]ready[/green] {resource_name}: {source}")
