from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_dashboard.experiments import (
    discover_experiment_runs,
    load_run_results,
    load_sample_artifacts,
)
from data_dashboard.models import DashboardConfig
from data_dashboard.ui import dataframe, error_box, path_caption


def _display_value(value: object, *, percent: bool = False) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    return f"{value:.2%}" if percent else f"{value:.4f}"


def render(config: DashboardConfig) -> None:
    st.title("Experiment Results")
    st.caption("Compare Pi Bench runs and inspect individual agent trajectories and scores.")
    path_caption(config.experiment_root)

    runs = discover_experiment_runs(config.experiment_root)
    if not runs:
        st.info(
            "No Pi Bench runs found. Run `pi-bench eval` or `pi-bench suite` and refresh this page."
        )
        return

    frame = pd.DataFrame(runs)
    benchmarks = sorted(value for value in frame["benchmark"].dropna().unique())
    selected_benchmarks = st.multiselect("Benchmarks", benchmarks, default=benchmarks)
    filtered = frame[frame["benchmark"].isin(selected_benchmarks)] if selected_benchmarks else frame

    completed = int((filtered["status"] == "completed").sum())
    attempted = int(filtered["attempted_count"].fillna(0).sum())
    timeouts = int(filtered["agent_timeouts"].fillna(0).sum())
    mean_tool_error = filtered["tool_error_rate"].dropna().mean()
    metrics = st.columns(4)
    metrics[0].metric("Runs", len(filtered))
    metrics[1].metric("Completed runs", completed)
    metrics[2].metric("Attempted samples", f"{attempted:,}")
    metrics[3].metric(
        "Mean tool-error rate",
        "N/A" if pd.isna(mean_tool_error) else f"{mean_tool_error:.2%}",
        help=f"Timeouts across selected runs: {timeouts}",
    )

    display_columns = [
        "run_id",
        "benchmark",
        "task_type",
        "model",
        "status",
        "primary_metric_name",
        "primary_metric_value",
        "completed_count",
        "attempted_count",
        "agent_timeouts",
        "mean_latency_seconds",
        "tool_error_rate",
        "total_tokens",
    ]
    dataframe(filtered[display_columns], height=min(420, 80 + len(filtered) * 35))

    chartable = filtered.dropna(subset=["primary_metric_value"])
    if not chartable.empty:
        st.warning(
            "Primary metrics with different names are shown together but are not "
            "directly comparable."
        )
        figure = px.bar(
            chartable,
            x="run_id",
            y="primary_metric_value",
            color="benchmark",
            facet_row="primary_metric_name"
            if chartable["primary_metric_name"].nunique() > 1
            else None,
            hover_data=["model", "completed_count", "agent_timeouts", "mean_latency_seconds"],
            title="Primary metric by run",
        )
        figure.update_layout(height=max(420, 260 * chartable["primary_metric_name"].nunique()))
        st.plotly_chart(figure, use_container_width=True)

    @st.fragment
    def render_drilldown() -> None:
        st.divider()
        st.subheader("Run and sample drill-down")
        run_labels = {f"{row['run_id']} · {row['benchmark']}": row for row in runs}
        selected_label = st.selectbox("Run", list(run_labels))
        selected_run = run_labels[selected_label]
        run_dir = Path(selected_run["run_dir"])

        try:
            results = load_run_results(run_dir, config.experiment_root)
        except Exception as exc:
            error_box(exc)
            return
        if not results:
            st.warning("This run has no results.jsonl yet; it may still be running.")
            return

        results_frame = pd.DataFrame(results)
        status_values = sorted(
            str(value) for value in results_frame["run_status"].dropna().unique()
        )
        selected_statuses = st.multiselect("Agent status", status_values, default=status_values)
        visible = results_frame[results_frame["run_status"].isin(selected_statuses)]
        dataframe(visible, height=360)
        if visible.empty:
            return

        sample_labels = {
            f"{row['sample_id']} · {row['run_status']} · {row['score_status']}": row
            for row in visible.to_dict(orient="records")
        }
        sample_label = st.selectbox("Sample", list(sample_labels))
        sample = sample_labels[sample_label]
        try:
            artifacts = load_sample_artifacts(
                run_dir,
                str(sample["item_dir"]),
                config.experiment_root,
            )
        except Exception as exc:
            error_box(exc)
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Agent status", sample.get("run_status", "N/A"))
        c2.metric("Score status", sample.get("score_status", "N/A"))
        c3.metric("Score", _display_value(sample.get("score")))
        c4.metric("Latency", f"{sample.get('duration_seconds', 0):.2f}s")

        st.markdown("#### Question")
        st.write(artifacts["input"].get("question", ""))
        left, right = st.columns(2)
        with left:
            st.markdown("#### Agent response")
            st.code(artifacts["final"] or "(empty)", language="text")
        with right:
            st.markdown("#### Score")
            st.json(artifacts["score"])
        with st.expander("Gold data and metadata"):
            st.json(artifacts["input"])
        with st.expander("Resolved prompt"):
            st.code(artifacts["prompt"], language="text")
        with st.expander("Tool trajectory and usage"):
            st.json({"tools": artifacts["tools"], "usage": artifacts["usage"]})
        if artifacts["stderr"]:
            with st.expander("Agent stderr"):
                st.code(artifacts["stderr"], language="text")

    render_drilldown()
