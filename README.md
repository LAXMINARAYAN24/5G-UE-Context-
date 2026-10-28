# 5G UE Context Desynchronization Detection and Recovery

A complete **abstract simulation prototype** for a protocol-aware RAN–Core context
verifier. It includes repeatable fault experiments, timestamped observation handling,
bounded reconciliation, baseline comparisons, tests, plots, and a Streamlit demonstration.
This implementation does not run a real gNB or 5G Core, send NGAP packets, or measure RF
performance. Context convergence is distinct from restoration of user connectivity.

## Run the project

### Final deliverables and Windows launcher

The final IEEE report is `deliverables/Final_IEEE_Report.pdf`, with editable
LaTeX source in `deliverables/Final_IEEE_Report.tex`. The final slides retain the
original proposal template: `deliverables/Final_Presentation_With_Graphs.pptx`.
The formal transition specification is in `research/formal_model.md`.
Fresh benchmark evidence is in `results/final-benchmark/` and test coverage in
`results/final-coverage.json`; older results remain available for comparison.

On this Windows machine, use the existing environment directly:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 app
powershell -ExecutionPolicy Bypass -File .\run.ps1 test
powershell -ExecutionPolicy Bypass -File .\run.ps1 demo
```

The launcher also accepts `benchmark` and `sensitivity`. It avoids the local
`uv run` trampoline error. For a fresh environment, install dependencies with
the locked setup command below first. Do not submit the old proposal PDF as the
final report: its broad accuracy and recovery claims lack the final qualifications.

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13 (uv can provision Python).
From this folder:

```sh
uv sync --locked --all-groups
uv run streamlit run app.py
```

The app prints its local URL. Choose a scenario, detector, and recovery setting, then
click **Run experiment**. Download the complete trace and results as JSON from the app.

```sh
# Reproduce the default example with recovery
uv run python -m ue_context.cli demo --config configs/demo.yaml
# Compare recovery on/off with the same seed
uv run python -m ue_context.cli demo --scenario loss_ack --seed 1 --out results/no-recovery
uv run python -m ue_context.cli demo --scenario loss_ack --seed 1 --recovery --out results/recovery
# Main benchmark: 12 scenarios × 40 seeds × 4 detector/recovery combinations
uv run python -m ue_context.cli benchmark --trials 40
# Sensitivity: 3 scenarios × 4 poll intervals × 3 grace settings × 20 held-out seeds
uv run python -m scripts.sensitivity
# Code and behavioral checks
make check
make test
```

## Contents

| File | Responsibility |
| --- | --- |
| `ue_context/model.py` | Context representation and three semantic contradiction rules |
| `ue_context/simulation.py` | Node procedures, faults, shared load queue, observation channel, oracle, recovery |
| `ue_context/verifier.py` | Snapshot ordering, freshness, temporal alignment, pending procedures, persistence, evidence |
| `ue_context/metrics.py` | Episode matching, false positives, latency, proxy probes, recovery and exposure |
| `ue_context/cli.py` | Demo exports and paired benchmark aggregation |
| `ue_context/plots.py` | Static figures from actual experiment results |
| `app.py` | Interactive demonstration and downloadable experiment data |
| `configs/demo.yaml` | Explicit default configuration |
| `tests/` | Model, detector, recovery, metrics, exports and dashboard tests |
| `results/benchmark/` | Raw runs, summary tables, figures and source hashes |
| `results/sensitivity.csv` | Observation interval and grace sensitivity results |
| `deliverables/Project_Pre_Report.docx` | Project explanation, reference comparison, measurements, limitations and viva answers |

## Model and assumptions

The procedure abstraction is inspired by 3GPP Release 16 session establishment,
resource modification and release. It is not an implementation of every NAS/NGAP step.
The Core object aggregates SMF/AMF responsibilities and owns committed QoS/resource
authorization. The RAN object owns its applied resource state. QoS integers are abstract
profile identifiers, not QFI or 5QI encodings. The logical session can remain established
when access resources deactivate. Modification without a committed session is rejected.

Each UE/session has its own transaction identity. An operation requests a RAN change,
then commits the Core's abstract state after completion processing. On application
timeout the Core retains its prior committed state. These commit/rollback semantics and
the 110 ms timeout are experimental choices, not mandatory 3GPP behavior.

The verifier receives complete snapshots with node sequence numbers, capture times,
and last-change timestamps. It has no access to fault tags or actual node memory.
It discards duplicate/older snapshots, refuses stale or temporally incompatible views,
waits for pending procedures, then requires sustained evidence for 12 ms by default.
The global simulator clock is an explicit assumption. Real monitoring would need
bounded clock skew, authenticated adapters and reliable identity correlation.

Recovery queries the nodes through a simulated adapter, refuses pending operations,
checks versions before writing, reconciles the RAN to the committed Core authorization,
and queries again to verify convergence. It retries at most twice per recovery job.
This is a custom experimental adapter, not a standardized "Context Sync Request".
Rollback may remove orphan resources and leave the UE without a session.

## Faults and controls

`clean`, `delay`, `loss_request`, `loss_ack`, `setup_loss_ack`, `release_loss_ack`,
`reorder_observations`, `high_load`, `observation_outage`, `idle_resume`, `intra_gnb`,
`recovery_failure`.

Loss scenarios represent application handling/completion failures. NGAP's reliable
SCTP transport is not replaced by an unrealistic unreliable transport. Reordering is
in the telemetry channel. The high-load scenario queues processing in a three-worker
resource and can produce genuine post-timeout divergence. The intra-gNB scenario only
changes the local cell, as a negative control; it does not simulate handover signaling.

## Reading results correctly

The oracle reads actual node states and labels contradictions only after pending
procedures end. The detector consumes snapshots only. Both use the same semantic
predicates, so the experiment checks monitor behavior under this model rather than
independently proving those predicates against the full standards.

An alarm is a true positive only if it matches the session and rule inside a truth
episode. Early alarms during valid transitions are false positives, even if a fault
appears later. A repeat alarm in one episode is counted separately as a duplicate.
False-positive rate uses sessions with **no truth episodes in that run**, not all sessions.
Undefined denominators appear as `null`/N/A. Aggregation pools counts, not averages of rates.

Probe times are fixed at 285, 335 and 510 virtual ms. These are **context consistency
proxies**, not actual packet delivery tests. A mutually inactive session passes the
consistency predicate and does not prove that a user can connect. Lead time is computed
only before a failed proxy probe in the same episode. Missing lead time is N/A.
The dashboard extends the horizon to 600 ms to accommodate its larger UE settings.

## Research and scope

See the pre-report and `research/references.md`. The conceptual reference chosen for
this implementation is *Data Consistency in the 5G Specification* (ICIN 2020).
The two KPI anomaly papers from the proposal are supporting references. This is an
engineering extension relative to those references, not a claim of worldwide novelty.
Full-paper replication, operator traces, hardware tests, and production recovery remain
outside this prototype. The supplied CI workflow has not been run on GitHub.

