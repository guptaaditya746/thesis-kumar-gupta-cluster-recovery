from __future__ import annotations

import pandas as pd
import streamlit as st

from data_dashboard.catalog import connect
from data_dashboard.models import DashboardConfig
from data_dashboard.ui import dataframe


def render(config: DashboardConfig) -> None:
    st.title("Benchmark ↔ Corpus Mapping")
    st.caption("Check whether benchmark and corpus artifacts are available under matching dataset IDs.")

    connection = connect(config, read_only=True)
    datasets = connection.execute(
        "SELECT dataset_id, dataset_name, artifact_type, root_path, error FROM datasets ORDER BY dataset_id"
    ).df()
    connection.close()
    if datasets.empty:
        st.info("The catalog is empty.")
        return

    rows = []
    for dataset_id, group in datasets.groupby("dataset_id"):
        benchmarks = group[group["artifact_type"] == "benchmark"]
        corpora = group[group["artifact_type"] == "corpus"]
        rows.append({
            "dataset_id": dataset_id,
            "benchmark_available": not benchmarks.empty,
            "benchmark_path": benchmarks["root_path"].iloc[0] if not benchmarks.empty else None,
            "corpus_available": not corpora.empty,
            "corpus_path": corpora["root_path"].iloc[0] if not corpora.empty else None,
            "status": "complete" if not benchmarks.empty and not corpora.empty else "partial",
        })
    dataframe(pd.DataFrame(rows))
    st.info(
        "Shared corpora, such as Wikipedia-18 or MS MARCO, may intentionally map to multiple benchmarks. "
        "Declare those relationships explicitly in config/dashboard.yaml when needed."
    )
