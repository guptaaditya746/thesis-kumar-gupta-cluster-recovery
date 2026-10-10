from __future__ import annotations

import os
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    service_root: Path
    data: dict[str, Any]

    @property
    def operation(self) -> str:
        value = self.data.get("operation")
        if not isinstance(value, str) or not value.strip():
            raise ConfigError("Top-level 'operation' must be a non-empty string")
        return value.strip().lower()

    def section(self, name: str) -> dict[str, Any]:
        value = self.data.get(name, {})
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ConfigError(f"Section [{name}] must be a TOML table")
        return value

    def resolve_path(self, value: str | Path | None) -> Path | None:
        if value is None:
            return None
        raw = os.path.expanduser(os.path.expandvars(str(value).strip()))
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = self.service_root / path
        return path.resolve()


def load_config(path: Path, *, service_root: Path) -> LoadedConfig:
    config_path = path.expanduser().resolve()
    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a TOML table")
    version = data.get("version", 1)
    if version != 1:
        raise ConfigError(f"Unsupported config version: {version!r}; expected 1")
    return LoadedConfig(path=config_path, service_root=service_root.resolve(), data=data)


def get_str(section: dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = section.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"'{key}' must be a string")
    return value


def get_bool(section: dict[str, Any], key: str, default: bool = False) -> bool:
    value = section.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"'{key}' must be a boolean")
    return value


def get_int(section: dict[str, Any], key: str, default: int | None = None) -> int | None:
    value = section.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"'{key}' must be an integer")
    return value


def get_float(section: dict[str, Any], key: str, default: float | None = None) -> float | None:
    value = section.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"'{key}' must be a number")
    return float(value)


def get_str_list(section: dict[str, Any], key: str) -> list[str]:
    value = section.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"'{key}' must be an array of strings")
    return list(value)
