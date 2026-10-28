"""Episode-based matching; undefined metrics use None, never invented zeroes."""

from statistics import mean


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def evaluate(episodes, alarms, probes, recoveries, duration, sessions, session_keys=None):
    matched = set()
    tp = fp = duplicate = 0
    delays = []
    leads = []
    for alarm in alarms:
        matches = [
            i
            for i, e in enumerate(episodes)
            if e.key == alarm.key
            and e.rule == alarm.rule
            and e.start <= alarm.time < (e.end if e.end is not None else duration)
        ]
        if not matches:
            fp += 1
            alarm.status = "false_positive"
        elif matches[0] in matched:
            duplicate += 1
            alarm.status = "duplicate"
        else:
            index = matches[0]
            matched.add(index)
            tp += 1
            alarm.status = "true_positive"
            episode = episodes[index]
            delays.append(alarm.time - episode.start)
            # Only a failing probe in the same truth episode qualifies.
            future = [
                p["time"]
                for p in probes
                if p["key"] == alarm.key
                and p["failed"]
                and alarm.time <= p["time"] < (episode.end or duration)
            ]
            if future:
                leads.append(min(future) - alarm.time)
    observed_keys = set(session_keys) if session_keys is not None else {p["key"] for p in probes}
    negative_keys = observed_keys - {e.key for e in episodes}
    false_keys = {a.key for a in alarms if a.status == "false_positive"}
    successes = sum(r["outcome"] == "success" for r in recoveries)
    return {
        "tp": tp,
        "fp": fp,
        "fn": len(episodes) - len(matched),
        "duplicates": duplicate,
        "truth_episodes": len(episodes),
        "alarm_count": len(alarms),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, len(episodes)),
        "negative_sessions": len(negative_keys),
        "false_positive_sessions": len(negative_keys & false_keys),
        "false_positive_rate": ratio(len(negative_keys & false_keys), len(negative_keys)),
        "mean_detection_delay_ms": mean(delays) if delays else None,
        "mean_lead_time_ms": mean(leads) if leads else None,
        "lead_time_samples": len(leads),
        "failed_probes": sum(p["failed"] for p in probes),
        "total_probes": len(probes),
        "recovery_successes": successes,
        "recovery_jobs": len(recoveries),
        "recovery_success_rate": ratio(successes, len(recoveries)),
        "mean_recovery_ms": mean(
            [r["end"] - r["start"] for r in recoveries if r["outcome"] == "success"]
        )
        if successes
        else None,
        "mismatch_exposure_ms": sum((e.end or duration) - e.start for e in episodes),
        "session_time_ms": duration * sessions,
    }
