"""Command-line demonstration and repeatable benchmark suite."""

import argparse
import csv
import hashlib
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path

import yaml

from .simulation import SCENARIOS, Config, run


def save_result(result, directory):
    directory.mkdir(parents=True, exist_ok=True)
    data = asdict(result)
    trace = data.pop("trace")
    (directory / "result.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    with (directory / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for event in trace:
            handle.write(json.dumps(event) + "\n")


def aggregate(rows):
    from .metrics import ratio

    sums = {
        field: sum(row[field] for row in rows)
        for field in (
            "tp",
            "fp",
            "fn",
            "duplicates",
            "negative_sessions",
            "false_positive_sessions",
            "truth_episodes",
            "failed_probes",
            "total_probes",
            "recovery_successes",
            "recovery_jobs",
            "mismatch_exposure_ms",
            "session_time_ms",
        )
    }
    sums["precision"] = ratio(sums["tp"], sums["tp"] + sums["fp"])
    sums["recall"] = ratio(sums["tp"], sums["truth_episodes"])
    sums["false_positive_rate"] = ratio(sums["false_positive_sessions"], sums["negative_sessions"])
    sums["recovery_success_rate"] = ratio(sums["recovery_successes"], sums["recovery_jobs"])
    for metric, weight in (
        ("mean_detection_delay_ms", "tp"),
        ("mean_lead_time_ms", "lead_time_samples"),
        ("mean_recovery_ms", "recovery_successes"),
    ):
        valid = [r for r in rows if r[metric] is not None]
        sums[metric] = ratio(
            sum(r[metric] * r[weight] for r in valid), sum(r[weight] for r in valid)
        )
    sums["mean_wall_ms"] = sum(r["wall_ms"] for r in rows) / len(rows)
    return sums


def suite(output, trials):
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario in SCENARIOS:
        for seed in range(1, trials + 1):
            for mode, recovery in (
                ("immediate", False),
                ("fixed", False),
                ("aware", False),
                ("aware", True),
            ):
                cfg = Config(scenario=scenario, seed=seed, recovery=recovery, record_trace=False)
                started = time.perf_counter()
                result = run(cfg, mode)
                rows.append(
                    {
                        "scenario": scenario,
                        "seed": seed,
                        "mode": mode,
                        "recovery": recovery,
                        **result.metrics,
                        "wall_ms": (time.perf_counter() - started) * 1000,
                    }
                )
    with (output / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for scenario in SCENARIOS:
        for mode, recovery in (
            ("immediate", False),
            ("fixed", False),
            ("aware", False),
            ("aware", True),
        ):
            group = [
                r
                for r in rows
                if r["scenario"] == scenario and r["mode"] == mode and r["recovery"] == recovery
            ]
            summary.append(
                {
                    "scenario": scenario,
                    "mode": mode,
                    "recovery": recovery,
                    "trials": trials,
                    **aggregate(group),
                }
            )
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    package_dir = Path(__file__).resolve().parent
    hashes = {
        f"ue_context/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package_dir.glob("*.py")
    }
    metadata = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "trials": trials,
        "run_count": len(rows),
        "configuration": asdict(Config()),
        "source_sha256": hashes,
        "comparison": "Paired seeds, complete-snapshot observations, synthetic node model",
        "timestamp_resolution_ms": 2,
        "note": "Wall time is local runtime, not production monitor latency.",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    from .plots import plot_suite

    plot_suite(summary, output)
    print(json.dumps({"runs": len(rows), "output": str(output)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="5G UE context consistency simulation")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--scenario", choices=SCENARIOS, default="loss_ack")
    demo.add_argument("--mode", choices=("immediate", "fixed", "aware"), default="aware")
    demo.add_argument("--seed", type=int, default=1)
    demo.add_argument("--recovery", action="store_true")
    demo.add_argument("--config", type=Path)
    demo.add_argument("--out", type=Path, default=Path("results/demo"))
    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--trials", type=int, default=40)
    benchmark.add_argument("--out", type=Path, default=Path("results/benchmark"))
    args = parser.parse_args()
    if args.command == "benchmark":
        if args.trials < 1:
            parser.error("trials must be positive")
        suite(args.out, args.trials)
    else:
        options = (
            yaml.safe_load(args.config.read_text())
            if args.config
            else {"scenario": args.scenario, "seed": args.seed, "recovery": args.recovery}
        )
        if not isinstance(options, dict):
            parser.error("configuration must be a YAML mapping")
        result = run(Config(**options), args.mode)
        save_result(result, args.out)
        print(json.dumps(result.metrics, indent=2))


if __name__ == "__main__":
    main()
