from __future__ import annotations

import argparse
import os
import subprocess
import shutil
import sys
from pathlib import Path

from .command import build_command, shell_preview
from .config import ConfigError, get_bool, get_int, get_str, load_config
from .logging import configure_logging, get_logger


def service_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "scripts").exists():
            return parent
    env_root = os.environ.get("DCI_SERVICE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path.cwd().resolve()


def artifact_root(cfg) -> Path | None:
    if cfg.operation == "single":
        return cfg.resolve_path(get_str(cfg.section("run"), "output_dir"))
    if cfg.operation == "benchmark":
        return cfg.resolve_path(get_str(cfg.section("benchmark"), "output_root"))
    return None


def snapshot_invocation(cfg, command: list[str]) -> None:
    target = artifact_root(cfg)
    if target is None or not target.exists():
        return
    shutil.copy2(cfg.path, target / "service-config.toml")
    (target / "service-command.txt").write_text(
        shell_preview(command) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dci-service",
        description="Config-driven standalone facade for DCI-Agent-Lite.",
    )
    parser.add_argument("--config", required=True, type=Path, help="TOML service config")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and print the resolved command only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = service_root()
    try:
        cfg = load_config(args.config, service_root=root)
        log_cfg = cfg.section("logging")
        configure_logging(
            level=get_str(log_cfg, "level", "INFO") or "INFO",
            json_logs=get_bool(log_cfg, "json", False),
        )
        log = get_logger("dci.service")
        command = build_command(cfg)
    except ConfigError as exc:
        configure_logging()
        get_logger("dci.service").error("config_invalid", error=str(exc), config=str(args.config))
        return 2

    log.info(
        "config_loaded",
        config=str(cfg.path),
        operation=cfg.operation,
        service_root=str(root),
    )
    log.info("command_resolved", command=shell_preview(command))

    if args.dry_run:
        log.info("dry_run_complete")
        return 0

    env = os.environ.copy()
    pi = cfg.section("pi")
    node_heap = get_int(pi, "node_max_old_space_size_mb")
    if node_heap is not None and cfg.operation in {"single", "terminal"}:
        existing = env.get("NODE_OPTIONS", "").strip()
        heap_arg = f"--max-old-space-size={node_heap}"
        env["NODE_OPTIONS"] = f"{existing} {heap_arg}".strip() if existing else heap_arg

    log.info("operation_started", operation=cfg.operation)
    try:
        completed = subprocess.run(command, cwd=str(root), env=env, check=False)
    except KeyboardInterrupt:
        log.warning("operation_interrupted", operation=cfg.operation)
        return 130
    except OSError as exc:
        log.error("operation_launch_failed", operation=cfg.operation, error=str(exc), exc_info=True)
        return 1

    try:
        snapshot_invocation(cfg, command)
    except OSError as exc:
        log.warning("invocation_snapshot_failed", error=str(exc))

    if completed.returncode == 0:
        log.info("operation_completed", operation=cfg.operation, returncode=completed.returncode)
    else:
        log.error("operation_failed", operation=cfg.operation, returncode=completed.returncode)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
