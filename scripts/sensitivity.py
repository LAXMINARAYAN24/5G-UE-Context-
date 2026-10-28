"""Vary observation interval and persistence grace on held-out seeds."""

import csv
from pathlib import Path

from ue_context.cli import aggregate
from ue_context.simulation import Config, run


def main():
    rows = []
    for scenario in ("loss_ack", "delay", "reorder_observations"):
        for poll in (5, 15, 30, 90):
            for grace in (0, 12, 24):
                runs = []
                for seed in range(101, 121):
                    result = run(
                        Config(
                            scenario=scenario,
                            poll_ms=poll,
                            grace_ms=grace,
                            seed=seed,
                            record_trace=False,
                        )
                    )
                    runs.append({**result.metrics, "wall_ms": 0})
                rows.append(
                    {
                        "scenario": scenario,
                        "poll_ms": poll,
                        "grace_ms": grace,
                        "trials": 20,
                        **aggregate(runs),
                    }
                )
    path = Path("results/sensitivity.csv")
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"720 held-out runs written to {path}")


if __name__ == "__main__":
    main()
