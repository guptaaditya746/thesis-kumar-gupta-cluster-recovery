from __future__ import annotations

import humanize
import plotly.express as px
import streamlit as st

from data_dashboard.catalog import connect
from data_dashboard.models import DashboardConfig
from data_dashboard.ui import dataframe


def render(config: DashboardConfig) -> None:
    st.title("Data Overview")
    st.caption("A read-only view of processed benchmarks, corpora, and their storage footprint.")

    connection = connect(config, read_only=True)
    datasets = connection.execute("SELECT * FROM datasets ORDER BY artifact_type, dataset_name").df()
    files = connection.execute("SELECT COUNT(*) AS n FROM files").fetchone()[0]
    connection.close()

    total_size = int(datasets["total_size_bytes"].fillna(0).sum()) if not datasets.empty else 0
    errors = int(datasets["error"].notna().sum()) if not datasets.empty else 0
    truncated = int(datasets["scan_truncated"].fillna(False).sum()) if not datasets.empty else 0

    columns = st.columns(5)
    columns[0].metric("Artifacts", len(datasets))
    columns[1].metric("Cataloged files", f"{files:,}")
    columns[2].metric("Storage", humanize.naturalsize(total_size, binary=True))
    columns[3].metric("Errors", errors)
    columns[4].metric("Truncated scans", truncated)

    if datasets.empty:
        st.info("No processed datasets are cataloged yet. Run `data-dashboard catalog build`.")
        return

    display = datasets[[
        "dataset_name", "artifact_type", "root_path", "scanned_file_count",
        "total_size_bytes", "record_count", "exact_record_count", "scan_truncated", "error"
    ]].copy()
    display["storage"] = display["total_size_bytes"].fillna(0).map(
        lambda value: humanize.naturalsize(int(value), binary=True)
    )
    display = display.drop(columns=["total_size_bytes"])
    dataframe(display)

    left, right = st.columns(2)
    with left:
        size_frame = datasets.copy()
        size_frame["size_gib"] = size_frame["total_size_bytes"].fillna(0) / (1024**3)
        figure = px.bar(
            size_frame,
            x="dataset_name",
            y="size_gib",
            color="artifact_type",
            title="Storage by artifact",
            labels={"dataset_name": "Dataset", "size_gib": "GiB"},
        )
        st.plotly_chart(figure, use_container_width=True)
    with right:
        count_frame = datasets.groupby("artifact_type", as_index=False)["scanned_file_count"].sum()
        figure = px.pie(
            count_frame,
            names="artifact_type",
            values="scanned_file_count",
            title="Cataloged files by type",
        )
        st.plotly_chart(figure, use_container_width=True)
