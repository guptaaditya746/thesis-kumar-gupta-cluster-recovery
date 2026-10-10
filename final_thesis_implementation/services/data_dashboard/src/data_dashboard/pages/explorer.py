from __future__ import annotations

from pathlib import Path

import streamlit as st

from data_dashboard.catalog import connect
from data_dashboard.models import DashboardConfig
from data_dashboard.readers import preview_file
from data_dashboard.ui import dataframe, error_box, path_caption
from data_dashboard.utils import safe_resolve


def render(config: DashboardConfig) -> None:
    st.title("Dataset Explorer")
    st.caption("Preview records lazily without loading complete datasets into memory.")

    connection = connect(config, read_only=True)
    datasets = connection.execute(
        "SELECT dataset_key, dataset_name, artifact_type, root_path FROM datasets "
        "ORDER BY artifact_type, dataset_name"
    ).df()
    if datasets.empty:
        connection.close()
        st.info("The catalog is empty.")
        return

    datasets["label"] = datasets.apply(
        lambda row: f"{row['dataset_name']} · {row['artifact_type']}", axis=1
    )
    selected_label = st.selectbox("Artifact", datasets["label"].tolist())
    selected_key = datasets.loc[datasets["label"] == selected_label, "dataset_key"].iloc[0]
    selected_root = Path(
        str(datasets.loc[datasets["label"] == selected_label, "root_path"].iloc[0])
    )

    filter_text = st.text_input("Filter filenames", placeholder="jsonl, shard name, split...")
    like = f"%{filter_text}%"
    file_rows = connection.execute(
        """SELECT relative_path, absolute_path, format, size_bytes, record_count
           FROM files WHERE dataset_key = ? AND relative_path ILIKE ?
           ORDER BY relative_path LIMIT 500""",
        [selected_key, like],
    ).df()
    connection.close()

    if file_rows.empty:
        st.warning("No matching files found.")
        return

    selected_relative = st.selectbox("File", file_rows["relative_path"].tolist())
    row = file_rows.loc[file_rows["relative_path"] == selected_relative].iloc[0]
    path = Path(str(row["absolute_path"]))
    path = safe_resolve(path, [config.processed_root, selected_root])
    path_caption(path)

    limit = st.slider(
        "Preview rows",
        min_value=1,
        max_value=config.preview.maximum_rows,
        value=min(config.preview.default_rows, config.preview.maximum_rows),
        step=10,
    )
    try:
        frame = preview_file(path, limit=limit)
        keyword = st.text_input("Filter preview values", placeholder="Search within loaded rows")
        if keyword:
            mask = (
                frame.astype(str)
                .apply(lambda column: column.str.contains(keyword, case=False, na=False))
                .any(axis=1)
            )
            frame = frame.loc[mask]
        st.write(f"Showing {len(frame):,} rows and {len(frame.columns):,} columns")
        dataframe(frame)
        if config.safety.allow_sample_download:
            st.download_button(
                "Download displayed sample as CSV",
                data=frame.to_csv(index=False).encode("utf-8"),
                file_name=f"{path.stem}_sample.csv",
                mime="text/csv",
            )
    except Exception as exc:
        error_box(exc)
