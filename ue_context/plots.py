"""Static scientific figures for reproducible experiment outputs."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_suite(summary, directory):
    selected = [
        r
        for r in summary
        if r["scenario"] in {"clean", "delay", "high_load", "idle_resume"} and not r["recovery"]
    ]
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    scenarios = list(dict.fromkeys(r["scenario"] for r in selected))
    for offset, mode in enumerate(("immediate", "fixed", "aware")):
        values = [
            next(
                r["false_positive_rate"]
                for r in selected
                if r["scenario"] == s and r["mode"] == mode
            )
            for s in scenarios
        ]
        ax.bar(
            [i + (offset - 1) * 0.25 for i in range(len(scenarios))], values, width=0.25, label=mode
        )
    ax.set_xticks(range(len(scenarios)), scenarios)
    ax.set_ylabel("False-positive session rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("False alarms on sessions without truth episodes")
    ax.legend()
    fig.savefig(directory / "false_positives.png", dpi=180)
    plt.close(fig)
    selected = [
        r
        for r in summary
        if r["scenario"]
        in {
            "loss_ack",
            "setup_loss_ack",
            "release_loss_ack",
            "observation_outage",
            "recovery_failure",
        }
        and r["mode"] == "aware"
    ]
    scenarios = list(dict.fromkeys(r["scenario"] for r in selected))
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    for offset, recovery in enumerate((False, True)):
        values = [
            next(
                r["failed_probes"] / r["total_probes"]
                for r in selected
                if r["scenario"] == s and r["recovery"] == recovery
            )
            for s in scenarios
        ]
        ax.bar(
            [i + (offset - 0.5) * 0.35 for i in range(len(scenarios))],
            values,
            width=0.35,
            label="recovery on" if recovery else "recovery off",
        )
    ax.set_xticks(range(len(scenarios)), scenarios, rotation=12)
    ax.set_ylabel("Fraction of synthetic service probes that failed")
    ax.set_ylim(0, 1)
    ax.set_title("Recovery effectiveness and observation limits")
    ax.legend()
    fig.savefig(directory / "recovery.png", dpi=180)
    plt.close(fig)
