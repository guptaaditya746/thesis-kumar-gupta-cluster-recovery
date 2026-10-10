from __future__ import annotations

import streamlit as st

from data_dashboard.catalog import build_catalog, catalog_exists
from data_dashboard.config import load_config
from data_dashboard.pages import (
    corpus,
    experiments,
    explorer,
    manifests,
    mapping,
    overview,
    quality,
)
from data_dashboard.ui import configure_page, error_box


def main() -> None:
    configure_page()
    try:
        config = load_config()
    except Exception as exc:
        st.title("Thesis Data Observatory")
        error_box(exc)
        st.stop()

    st.sidebar.title("DATA OBSERVATORY")
    st.sidebar.markdown("`BIOS v0.1` · **READ ONLY**")
    st.sidebar.caption(f"DATA ROOT · {config.processed_root.name.upper()}")
    with st.sidebar.expander("Data location"):
        st.code(str(config.processed_root), language="text")

    pages = {
        "[01] Experiment Results": experiments.render,
        "[02] Overview": overview.render,
        "[03] Dataset Explorer": explorer.render,
        "[04] Corpus Browser": corpus.render,
        "[05] Data Quality": quality.render,
        "[06] Manifests": manifests.render,
        "[07] Benchmark ↔ Corpus": mapping.render,
    }
    selected = st.sidebar.radio("Navigate", list(pages))

    if st.sidebar.button("[R] Scan new data", type="primary", use_container_width=True):
        with st.sidebar.status("Scanning processed data...", expanded=True) as status:
            try:
                totals = build_catalog(config, new_sources_only=True, scan_limit=5_000)
                status.update(
                    label=(f"Ready: {totals['datasets']} artifacts, {totals['files']:,} files"),
                    state="complete",
                )
                st.rerun()
            except Exception as exc:
                status.update(label="Data scan failed", state="error")
                st.sidebar.error(str(exc))

    if selected != "[01] Experiment Results" and not catalog_exists(config):
        st.warning("No catalog exists yet. Build it before exploring processed data.")
        if st.button("Build catalog now", type="primary"):
            with st.spinner("Scanning processed data..."):
                try:
                    totals = build_catalog(config)
                    st.success(
                        f"Cataloged {totals['datasets']} artifacts and {totals['files']} files."
                    )
                    st.rerun()
                except Exception as exc:
                    error_box(exc)
        st.stop()

    st.sidebar.divider()
    st.sidebar.caption(f"Config: `{config.config_path}`")
    st.sidebar.caption("Processed data is never modified.")
    pages[selected](config)


if __name__ == "__main__":
    main()
