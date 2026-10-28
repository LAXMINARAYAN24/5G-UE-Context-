"""Interactive laboratory demonstration, never presented as live 5G telemetry."""

import json
from dataclasses import asdict

import pandas as pd
import streamlit as st

from ue_context.simulation import SCENARIOS, Config, run


st.set_page_config(page_title="5G UE Context Lab", layout="wide")
st.title("5G UE Context Detection and Recovery")
st.write("An abstract protocol-state simulation. Times are virtual milliseconds.")

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
    probability = st.slider(
        "Fraction of sessions eligible for the fault", 0.0, 1.0, 0.7
    )
    timeout = st.slider("Procedure timeout in ms", 90, 130, 110)
    clicked = st.button("Run experiment", type="primary")

if clicked or "result" not in st.session_state:
    st.session_state.result = run(
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
        ),
        mode,
    )
result = st.session_state.result
st.caption(
    f"Displayed run: {result.config['scenario']}, {result.mode}, seed {result.config['seed']}"
)
columns = st.columns(4)
for column, name in zip(
    columns, ("precision", "recall", "failed_probes", "recovery_success_rate"), strict=True
):
    value = result.metrics[name]
    column.metric(name.replace("_", " ").title(), "N/A" if value is None else f"{value:.3g}")
st.write(
    "N/A means the experiment has no applicable denominator. Perfect scores on these controlled scenarios do not establish real-network performance."
)
key = st.selectbox("UE and session", list(result.final_states))
trace = pd.DataFrame([e for e in result.trace if e["key"] == key])
observations = trace[trace["event"] == "observation"]
if not observations.empty:
    timeline = observations.pivot_table(
        index="time_ms", columns="side", values="qos", aggfunc="last"
    ).ffill()
    st.subheader("Observed QoS profiles")
    st.line_chart(timeline)
st.subheader("Alarms with evidence")
st.dataframe(pd.DataFrame([a for a in result.alarms if a["key"] == key]), width="stretch")
st.subheader("Event timeline")
st.dataframe(trace.dropna(axis=1, how="all"), width="stretch", height=380)
with st.expander("Independent ground truth and metrics"):
    st.json({"episodes": result.episodes, "metrics": result.metrics})
with st.expander("Final node state"):
    st.json(result.final_states[key])
st.download_button(
    "Download experiment JSON",
    json.dumps(asdict(result), indent=2),
    "experiment.json",
    "application/json",
)
