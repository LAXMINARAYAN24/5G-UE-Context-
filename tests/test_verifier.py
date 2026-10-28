from ue_context.model import Context, Snapshot, contradictions
from ue_context.verifier import Verifier


def snapshot(side, context, seq=1, at=0, key="u/s"):
    return Snapshot(key, side, seq, at, context)


def test_idle_session_is_compatible_with_absent_access_resources():
    assert not contradictions(Context(rrc="IDLE"), Context(session=True))


def test_qos_rule_requires_active_resources_on_both_sides():
    assert not contradictions(Context(qos=1), Context(session=True, qos=2))
    assert contradictions(
        Context(resources=True, qos=1), Context(session=True, resources=True, qos=2)
    ) == ("QOS_PROFILE_MISMATCH",)


def test_known_procedure_suppresses_transient_then_detects_after_timeout():
    verifier = Verifier(grace_ms=10)
    verifier.ingest(snapshot("ran", Context(session=True, resources=True, qos=2)))
    verifier.ingest(
        snapshot(
            "core", Context(session=True, resources=True, qos=1, pending="modify", deadline=30)
        )
    )
    assert not verifier.check(20)
    assert not verifier.check(32)  # pre-deadline snapshot cannot prove completion
    verifier.ingest(snapshot("core", Context(session=True, resources=True, qos=1), 2, 32))
    verifier.ingest(snapshot("ran", Context(session=True, resources=True, qos=2), 2, 32))
    assert not verifier.check(32)
    alarms = verifier.check(42)
    assert len(alarms) == 1
    assert alarms[0].rule == "QOS_PROFILE_MISMATCH"
    assert not verifier.check(44)  # de-duplicate persistent alarm


def test_stale_duplicate_and_out_of_order_snapshots_are_discarded():
    verifier = Verifier()
    latest = Context(session=True, resources=True, qos=2)
    verifier.ingest(snapshot("ran", latest, 3, 20))
    verifier.ingest(snapshot("ran", Context(), 2, 10))
    verifier.ingest(snapshot("ran", Context(), 3, 15))
    assert verifier.views["u/s"]["ran"].context.qos == 2
    assert verifier.discarded == 2


def test_missing_telemetry_is_unknown_and_resets_persistence_evidence():
    verifier = Verifier(grace_ms=10, freshness_ms=20)
    verifier.ingest(snapshot("ran", Context(resources=True)))
    verifier.ingest(snapshot("core", Context()))
    assert not verifier.check(0)
    assert not verifier.check(22)
    assert verifier.unknown_checks == 1
    verifier.ingest(snapshot("ran", Context(resources=True), 2, 25))
    verifier.ingest(snapshot("core", Context(), 2, 25))
    assert not verifier.check(25)
    assert len(verifier.check(35)) == 1


def test_sessions_do_not_share_evidence():
    verifier = Verifier(grace_ms=0)
    for key in ("u/1", "u/2"):
        verifier.ingest(snapshot("ran", Context(resources=True), key=key))
        verifier.ingest(snapshot("core", Context(session=True, resources=key == "u/2"), key=key))
    assert [alarm.key for alarm in verifier.check(1)] == ["u/1"]


def test_temporally_incompatible_snapshots_are_unknown_until_aligned():
    verifier = Verifier(grace_ms=0)
    verifier.ingest(snapshot("ran", Context(session=True, resources=True, qos=1), at=5))
    verifier.ingest(
        snapshot("core", Context(session=True, resources=True, qos=2, changed_at=10), at=15)
    )
    assert not verifier.check(16)
    assert verifier.unknown_checks == 1
    verifier.ingest(
        snapshot("ran", Context(session=True, resources=True, qos=2, changed_at=8), 2, 15)
    )
    assert not verifier.check(17)
