from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_dashboard.catalog import connect
from data_dashboard.models import DashboardConfig
from data_dashboard.profiling import infer_semantic_columns, profile_file
from data_dashboard.ui import dataframe, error_box, path_caption
from data_dashboard.utils import safe_resolve


def render(config: DashboardConfig) -> None:
    st.title("Data Quality")
    st.caption("Sample-based schema, missingness, duplicate, and text-length diagnostics.")

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
    label = st.selectbox("Artifact", datasets["label"].tolist(), key="quality_artifact")
    key = datasets.loc[datasets["label"] == label, "dataset_key"].iloc[0]
    selected_root = Path(str(datasets.loc[datasets["label"] == label, "root_path"].iloc[0]))
    files = connection.execute(
        """SELECT relative_path, absolute_path, format, size_bytes
           FROM files WHERE dataset_key = ? ORDER BY size_bytes DESC LIMIT 1000""",
        [key],
    ).df()
    connection.close()

    if files.empty:
        st.warning("No files available for profiling.")
        return
    selected = st.selectbox("File to profile", files["relative_path"].tolist())
    absolute = Path(files.loc[files["relative_path"] == selected, "absolute_path"].iloc[0])
    absolute = safe_resolve(absolute, [config.processed_root, selected_root])
    path_caption(absolute)

    sample_rows = st.number_input(
        "Maximum sample rows",
        min_value=100,
        max_value=config.preview.quality_sample_rows,
        value=min(10000, config.preview.quality_sample_rows),
        step=100,
    )
    if st.button("Run quality profile", type="primary"):
        try:
            frame, report = profile_file(absolute, int(sample_rows))
            semantics = infer_semantic_columns(frame)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Sample rows", f"{report['sample_rows']:,}")
            c2.metric("Columns", report["column_count"])
            c3.metric("Duplicate rows", report["duplicate_rows"])
            c4.metric(
                "Duplicate IDs",
                report["duplicate_ids"] if report["duplicate_ids"] is not None else "N/A",
            )

            st.subheader("Detected semantic columns")
            st.json(semantics)

            missing = pd.DataFrame(
                [
                    {
                        "column": column,
                        "missing": count,
                        "missing_percent": (count / max(len(frame), 1)) * 100,
                    }
                    for column, count in report["missing_values"].items()
                ]
            ).sort_values("missing", ascending=False)
            st.subheader("Missing values")
            dataframe(missing)
            if not missing.empty:
                figure = px.bar(
                    missing, x="column", y="missing_percent", title="Missing values by column"
                )
                st.plotly_chart(figure, use_container_width=True)

            lengths = []
            for column, values in report["text_lengths"].items():
                lengths.append({"column": column, **values})
            if lengths:
                st.subheader("Text lengths")
                dataframe(pd.DataFrame(lengths))

            with st.expander("Sample data"):
                dataframe(frame.head(200))
        except Exception as exc:
            error_box(exc)
