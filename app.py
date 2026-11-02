"""Interactive laboratory demonstration, never presented as live 5G telemetry."""

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from ue_context.simulation import SCENARIOS, Config, run


def display_metric(value, suffix=""):
    return "N/A" if value is None else f"{value:.3g}{suffix}"


@st.cache_data
def load_benchmark_summary(path):
    return pd.read_csv(path)


st.set_page_config(page_title="5G UE Context Lab", layout="wide")
st.title("5G UE Context Detection and Recovery")
st.write(
    "An abstract protocol-state simulation. Times are virtual milliseconds; "
    "this dashboard does not show live network telemetry."
)

with st.sidebar:
    scenario = st.selectbox("Scenario", SCENARIOS, index=3)
    mode = st.selectbox("Detector", ("aware", "fixed", "immediate"))

    if mode == "aware":
        grace = st.slider(
            "Persistence grace (ms)",
            min_value=0,
            max_value=40,
            value=12,
            help="Minimum persistence time before the aware detector raises an alarm.",
        )
    elif mode == "fixed":
        grace = 12
        st.caption("Fixed waiting threshold: 25 ms")
    else:
        grace = 12
        st.caption("Immediate detector: no persistence waiting threshold.")

    seed = st.number_input("Random seed", 1, 100000, 1)
    ues = st.slider("UEs", 1, 10, 3)
    sessions = st.slider("Sessions per UE", 1, 5, 2)
    recovery = st.checkbox("Enable simulated recovery", value=True)
    probability = st.slider("Fraction of sessions eligible for the fault", 0.0, 1.0, 0.7)
    timeout = st.slider("Procedure timeout in ms", 90, 130, 110)
    clicked = st.button("Run experiment", type="primary")

current_config = asdict(
    Config(
        scenario=scenario,
        seed=int(seed),
        ues=ues,
        sessions_per_ue=sessions,
        duration_ms=600,
        recovery=recovery,
        fault_probability=probability,
        grace_ms=grace,
        procedure_timeout_ms=timeout,
    )
)
if clicked or "result" not in st.session_state:
    st.session_state.result = run(Config(**current_config), mode)

result = st.session_state.result
settings_changed = result.config != current_config or result.mode != mode
st.caption(
    f"Displayed run: {result.config['scenario']}, {result.mode}, seed {result.config['seed']}."
)
if settings_changed:
    st.warning(
        "Sidebar settings have changed. Click **Run experiment** to update the displayed results."
    )
else:
    st.success("Displayed results match the current sidebar settings.")

metrics = result.metrics
with st.container(horizontal=True):
    st.metric(
        "Precision",
        display_metric(None if metrics["precision"] is None else metrics["precision"] * 100, "%"),
        border=True,
    )
    st.metric(
        "Recall",
        display_metric(None if metrics["recall"] is None else metrics["recall"] * 100, "%"),
        border=True,
    )
    st.metric(
        "False-positive session rate",
        display_metric(
            None
            if metrics["false_positive_rate"] is None
            else metrics["false_positive_rate"] * 100,
            "%",
        ),
        border=True,
    )
    st.metric(
        "Mean detection delay",
        display_metric(metrics["mean_detection_delay_ms"], " ms"),
        border=True,
    )
with st.container(horizontal=True):
    st.metric(
        "Failed consistency probes",
        f"{metrics['failed_probes']} / {metrics['total_probes']}",
        border=True,
    )
    st.metric(
        "Mismatch exposure",
        display_metric(metrics["mismatch_exposure_ms"], " ms"),
        border=True,
    )
    st.metric(
        "Recovery success rate",
        display_metric(
            None
            if metrics["recovery_success_rate"] is None
            else metrics["recovery_success_rate"] * 100,
            "%",
        ),
        border=True,
    )
    st.metric("Alarm count", metrics["alarm_count"], border=True)

st.caption(
    "N/A means the metric has no applicable denominator. Probes are synthetic "
    "context-consistency checks, not measurements of real traffic, RF quality, or connectivity."
)

overview_tab, explorer_tab, benchmark_tab = st.tabs(
    ("Run details", "Session explorer", "Benchmark comparison")
)

with overview_tab:
    st.subheader("Experiment configuration")
    st.json({"configuration": result.config, "detector": result.mode})
    st.subheader("Metric definitions")
    st.markdown(
        "- **Precision / recall:** episode-matched alarm quality for this simulation run.\n"
        "- **False-positive session rate:** sessions with false alarms among sessions with no "
        "ground-truth episode.\n"
        "- **Mismatch exposure:** total simulated time spent in a ground-truth mismatch.\n"
        "- **Recovery success:** state convergence in the simulator, not restoration of "
        "real user connectivity."
    )

with explorer_tab:
    st.subheader("Explore one UE session")
    keys = list(result.final_states)
    key = st.selectbox("UE and session", keys, key="session_filter")
    trace = pd.DataFrame([event for event in result.trace if event["key"] == key])

    if trace.empty:
        st.info("This run has no recorded trace events.")
    else:
        event_types = sorted(trace["event"].dropna().unique().tolist())
        filter_columns = st.columns(2)
        with filter_columns[0]:
            selected_events = st.multiselect(
                "Event types",
                event_types,
                default=event_types,
                key="event_filter",
            )
        duration = int(result.config["duration_ms"])
        with filter_columns[1]:
            time_range = st.slider(
                "Virtual time range (ms)",
                min_value=0,
                max_value=duration,
                value=(0, duration),
                key="time_filter",
            )

        filtered_trace = trace[
            trace["event"].isin(selected_events)
            & trace["time_ms"].between(time_range[0], time_range[1])
        ]
        observations = filtered_trace[filtered_trace["event"] == "observation"]
        if not observations.empty and "qos" in observations:
            timeline = observations.pivot_table(
                index="time_ms", columns="side", values="qos", aggfunc="last"
            ).ffill()
            st.subheader("Observed QoS profiles")
            st.line_chart(timeline, alt="Observed QoS profiles for RAN and Core over virtual time")

        alarms = pd.DataFrame([alarm for alarm in result.alarms if alarm["key"] == key])
        st.subheader("Alarms with evidence")
        if alarms.empty:
            st.info("No alarms were raised for this session.")
        else:
            st.dataframe(alarms, width="stretch", hide_index=True, alt="Alarms and evidence")

        st.subheader("Filtered event timeline")
        if filtered_trace.empty:
            st.info("No events match these filters.")
        else:
            st.dataframe(
                filtered_trace.dropna(axis=1, how="all"),
                width="stretch",
                height=380,
                hide_index=True,
                alt="Filtered simulation events for the selected UE session",
            )
    with st.expander("Final node state"):
        st.json(result.final_states[key])

with benchmark_tab:
    st.subheader("Checked-in benchmark comparison")
    st.write(
        "These results come from the project's precomputed final benchmark. "
        "Opening this view does not launch benchmark simulations."
    )
    benchmark_path = Path(__file__).resolve().parent / "results" / "final-benchmark" / "summary.csv"
    if not benchmark_path.is_file():
        st.error(f"Benchmark summary was not found: {benchmark_path}")
    else:
        benchmark = load_benchmark_summary(str(benchmark_path))
        benchmark_scenarios = benchmark["scenario"].dropna().unique().tolist()
        default_scenario = (
            benchmark_scenarios.index(result.config["scenario"])
            if result.config["scenario"] in benchmark_scenarios
            else 0
        )
        benchmark_scenario = st.selectbox(
            "Benchmark scenario",
            benchmark_scenarios,
            index=default_scenario,
            key="benchmark_scenario",
        )
        comparison = benchmark[benchmark["scenario"] == benchmark_scenario].copy()
        comparison["comparison"] = comparison.apply(
            lambda row: f"{row['mode']} / recovery {'on' if row['recovery'] else 'off'}",
            axis=1,
        )
        metric_options = {
            "False-positive session rate": "false_positive_rate",
            "Precision": "precision",
            "Recall": "recall",
            "Recovery success rate": "recovery_success_rate",
            "Mean detection delay (ms)": "mean_detection_delay_ms",
            "Failed probes": "failed_probes",
        }
        selected_metric = st.selectbox("Compare metric", list(metric_options))
        metric_column = metric_options[selected_metric]
        chart_data = comparison[["comparison", metric_column]].dropna()
        if chart_data.empty:
            st.info(f"{selected_metric} is N/A for every configuration in this scenario.")
        else:
            st.bar_chart(
                chart_data,
                x="comparison",
                y=metric_column,
                alt=f"{selected_metric} by detector and recovery configuration",
            )
        st.dataframe(
            comparison.drop(columns="comparison"),
            width="stretch",
            hide_index=True,
            alt=f"Precomputed benchmark summary for {benchmark_scenario}",
        )

with st.expander("Independent ground truth and run metrics"):
    st.json({"episodes": result.episodes, "metrics": result.metrics})

st.download_button(
    "Download experiment JSON",
    json.dumps(asdict(result), indent=2),
    "experiment.json",
    "application/json",
)
