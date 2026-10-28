import json
import sys

import pytest

from ue_context.cli import main, suite
from ue_context.metrics import evaluate
from ue_context.simulation import Episode
from ue_context.verifier import Alarm, Verifier


def test_cli_demo_writes_replayable_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["lab", "demo", "--recovery", "--out", str(tmp_path)])
    main()
    result = json.loads((tmp_path / "result.json").read_text())
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert result["metrics"]["tp"] > 0
    assert any(event["event"] == "recovery_result" for event in events)


def test_small_suite_exports_complete_comparisons_and_figures(tmp_path, monkeypatch):
    # Source provenance must survive invocation from outside the package folder.
    monkeypatch.chdir(tmp_path)
    suite(tmp_path, 2)
    summary = json.loads((tmp_path / "summary.json").read_text())
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert len(summary) == 48
    assert metadata["run_count"] == 96
    assert len(metadata["source_sha256"]) >= 5
    assert all(
        (tmp_path / f).stat().st_size > 1000
        for f in ("false_positives.png", "recovery.png", "runs.csv")
    )


def test_duplicate_alarm_not_double_counted():
    alarms = [Alarm("u", t, "r", 0, {}, {}) for t in (12, 13)]
    metrics = evaluate([Episode("u", "r", 10, 20)], alarms, [], [], 30, 1)
    assert metrics["tp"] == 1
    assert metrics["duplicates"] == 1


def test_invalid_detector_mode():
    with pytest.raises(ValueError):
        Verifier("invalid")
