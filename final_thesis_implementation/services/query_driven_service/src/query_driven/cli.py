from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import load_config
from .logging import configure_logging, get_logger
from .pipeline import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Config-driven Query-Driven Multimodal GraphRAG service")
    parser.add_argument("--config", required=True, type=Path, help="TOML service config")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and print resolved settings without running")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        cfg = load_config(args.config)
        configure_logging(cfg.logging)
        logger = get_logger(service="query_driven")
        logger.info("config_loaded", config=str(cfg.config_path), operation=cfg.runtime.operation)
        if args.dry_run:
            print(json.dumps(cfg.to_jsonable(), ensure_ascii=False, indent=2))
            return 0
        asyncio.run(run(cfg))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        try:
            get_logger(service="query_driven").exception("service_failed", error=str(exc))
        except Exception:
            print(f"query-driven failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
