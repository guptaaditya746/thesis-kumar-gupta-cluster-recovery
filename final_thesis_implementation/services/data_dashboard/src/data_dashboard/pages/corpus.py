from __future__ import annotations

from pathlib import Path

import streamlit as st

from data_dashboard.catalog import connect
from data_dashboard.models import DashboardConfig
from data_dashboard.readers import text_preview
from data_dashboard.search import ripgrep_search
from data_dashboard.ui import dataframe, error_box, path_caption
from data_dashboard.utils import safe_resolve


def render(config: DashboardConfig) -> None:
    st.title("Corpus Browser")
    st.caption("Find corpus files by path and run bounded content searches with ripgrep.")

    connection = connect(config, read_only=True)
    corpora = connection.execute(
        "SELECT dataset_key, dataset_name, root_path FROM datasets "
        "WHERE artifact_type = 'corpus' ORDER BY dataset_name"
    ).df()
    if corpora.empty:
        connection.close()
        st.info("No corpus artifacts are cataloged.")
        return

    selected_name = st.selectbox("Corpus", corpora["dataset_name"].tolist())
    selected = corpora.loc[corpora["dataset_name"] == selected_name].iloc[0]
    dataset_key = selected["dataset_key"]
    root_path = Path(str(selected["root_path"]))
    root = safe_resolve(root_path, [config.processed_root, root_path])

    tab_files, tab_search = st.tabs(["Browse files", "Search contents"])
    with tab_files:
        filter_text = st.text_input("Filename/path contains", key="corpus_file_filter")
        rows = connection.execute(
            """SELECT relative_path, absolute_path, format, size_bytes
               FROM files WHERE dataset_key = ? AND relative_path ILIKE ?
               ORDER BY relative_path LIMIT 500""",
            [dataset_key, f"%{filter_text}%"],
        ).df()
        if rows.empty:
            st.warning("No matching files.")
        else:
            relative = st.selectbox("Document/file", rows["relative_path"].tolist())
            absolute = Path(rows.loc[rows["relative_path"] == relative, "absolute_path"].iloc[0])
            absolute = safe_resolve(absolute, [config.processed_root, root])
            path_caption(absolute)
            try:
                st.code(
                    text_preview(absolute, config.preview.maximum_text_characters),
                    language="text",
                    wrap_lines=True,
                )
            except Exception as exc:
                error_box(exc)

    with tab_search:
        query = st.text_input("Search phrase", placeholder="Enter a literal phrase or regex")
        if st.button("Search corpus", type="primary", disabled=not query.strip()):
            try:
                results = ripgrep_search(
                    root=root,
                    query=query,
                    timeout_seconds=config.search.timeout_seconds,
                    maximum_matches=config.search.maximum_matches,
                    maximum_matches_per_file=config.search.maximum_matches_per_file,
                )
                if results.empty:
                    st.info("No matches found within the configured limits.")
                else:
                    dataframe(results, height=520)
            except Exception as exc:
                error_box(exc)
    connection.close()
