from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import yaml

from data_dashboard.models import DashboardConfig
from data_dashboard.ui import error_box, path_caption
from data_dashboard.utils import safe_resolve


def _manifest_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml"}
    )


def render(config: DashboardConfig) -> None:
    st.title("Manifests & Provenance")
    st.caption("Inspect source, preprocessing, checksum, and validation metadata.")

    files = _manifest_files(config.manifest_root)
    if not files:
        st.info(f"No JSON/YAML manifests found under `{config.manifest_root}`.")
        return

    relative = [str(path.relative_to(config.manifest_root)) for path in files]
    selected = st.selectbox("Manifest", relative)
    path = safe_resolve(config.manifest_root / selected, [config.manifest_root])
    path_caption(path)
    try:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            value = json.loads(raw)
        else:
            value = yaml.safe_load(raw)
        st.json(value, expanded=True)
        st.download_button(
            "Download manifest",
            data=raw.encode("utf-8"),
            file_name=path.name,
            mime="application/json" if path.suffix.lower() == ".json" else "text/yaml",
        )
    except Exception as exc:
        error_box(exc)
