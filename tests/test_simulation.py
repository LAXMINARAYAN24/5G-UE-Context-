import json
from dataclasses import asdict

import pytest

from ue_context.metrics import evaluate
from ue_context.simulation import SCENARIOS, Config, Episode, Experiment, run
from ue_context.verifier import Alarm


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_all_scenarios_terminate_and_serialize(scenario):
    result = run(Config(scenario=scenario, ues=1, sessions_per_ue=1))
    json.dumps(asdict(result))
    assert result.metrics["total_probes"] == 3
    assert all(e["end"] >= e["start"] for e in result.episodes)


@pytest.mark.parametrize("scenario", ["clean", "delay", "idle_resume", "intra_gnb", "loss_request"])
def test_benign_and_failed_request_controls_have_no_truth_desync(scenario):
    result = run(Config(scenario=scenario, fault_probability=1))
    assert result.metrics["truth_episodes"] == 0
    assert result.metrics["fp"] == 0
    assert result.metrics["recall"] is None


@pytest.mark.parametrize("scenario", ["loss_ack", "setup_loss_ack", "release_loss_ack"])
def test_completion_processing_failures_produce_detectable_desync(scenario):
    result = run(Config(scenario=scenario, fault_probability=1))
    assert result.metrics["truth_episodes"] == 6
    assert result.metrics["tp"] == 6
    assert result.metrics["fp"] == 0


def test_recovery_reduces_exposure_and_probe_failures():
    options = {"scenario": "loss_ack", "fault_probability": 1, "seed": 4}
    baseline = run(Config(**options))
    recovered = run(Config(**options, recovery=True))
    assert recovered.metrics["mismatch_exposure_ms"] < baseline.metrics["mismatch_exposure_ms"]
    assert recovered.metrics["failed_probes"] < baseline.metrics["failed_probes"]
    assert recovered.metrics["recovery_successes"] == 6


def test_failed_recovery_is_bounded_and_not_reported_as_success():
    result = run(Config(scenario="recovery_failure", recovery=True, fault_probability=1))
    assert result.metrics["recovery_successes"] == 0
    assert result.metrics["recovery_jobs"] == 6
    attempts = [e["attempt"] for e in result.trace if e["event"] == "recovery_query"]
    assert max(attempts) == 2


def test_same_seed_reproduces_trace_and_metrics():
    cfg = Config(scenario="reorder_observations", recovery=True, seed=9)
    assert asdict(run(cfg)) == asdict(run(cfg))


def test_short_horizon_retains_negative_session_denominator_without_probes():
    result = run(Config(scenario="clean", duration_ms=100))
    assert result.metrics["total_probes"] == 0
    assert result.metrics["negative_sessions"] == 6


def test_observation_outage_does_not_broadcast_truth_to_detector():
    result = run(Config(scenario="observation_outage", fault_probability=1))
    assert result.metrics["truth_episodes"] == 6
    assert result.metrics["unknown_checks"] > 0
    assert result.metrics["mean_detection_delay_ms"] > 60


def test_immediate_baseline_exposes_transient_false_alarms():
    cfg = Config(scenario="delay", fault_probability=0)
    assert run(cfg, "immediate").metrics["fp"] > 0
    assert run(cfg, "aware").metrics["fp"] == 0


def test_high_load_uses_shared_processing_queue():
    result = run(Config(scenario="high_load"))
    waits = [e["wait_ms"] for e in result.trace if e["event"] == "processing_queue"]
    assert max(waits) > 0


def test_reordered_observations_do_not_create_aware_false_alarms():
    for seed in range(1, 5):
        result = run(Config(scenario="reorder_observations", seed=seed))
        assert result.metrics["fp"] == 0
        assert result.metrics["snapshot_discards"] > 0


def test_modification_without_committed_session_is_rejected():
    result = run(Config(scenario="setup_loss_ack", fault_probability=1))
    assert any(e["event"] == "procedure_rejected" for e in result.trace)


def test_matching_does_not_credit_alarm_before_true_episode():
    alarm = Alarm("u/1", 9, "QOS_PROFILE_MISMATCH", 0, {}, {})
    metrics = evaluate([Episode("u/1", "QOS_PROFILE_MISMATCH", 10, 20)], [alarm], [], [], 30, 1)
    assert metrics["tp"] == 0
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1


def test_late_completion_cannot_commit_expired_transaction():
    experiment = Experiment(
        Config(scenario="delay", procedure_timeout_ms=5, ues=1, sessions_per_ue=1)
    )
    result = experiment.run()
    assert all(not states["core"]["session"] for states in result.final_states.values())
    assert any(event["event"] == "stale_request_rejected" for event in result.trace)


@pytest.mark.parametrize(
    "options",
    [
        {"ues": 0},
        {"scenario": "invalid"},
        {"poll_ms": 0},
        {"fault_probability": 2},
        {"grace_ms": -1},
    ],
)
def test_invalid_configuration_rejected(options):
    with pytest.raises(ValueError):
        run(Config(**options))
