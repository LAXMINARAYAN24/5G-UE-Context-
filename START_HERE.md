# Final project package

Open `deliverables/Final_Presentation_With_Graphs.pptx` for the 15-slide
presentation using the original proposal template. Use
`deliverables/Final_IEEE_Report.pdf` for the four-page IEEE conference report.
Editable source is `deliverables/Final_IEEE_Report.tex`; compile it twice with
pdfLaTeX from the deliverables folder. It uses IEEEtran and a chart in the results
folder. These files supersede the earlier redesigned slides and single-column report.

## Run the demonstration

Open PowerShell in this project folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 app
```

On this machine the environment already exists. On another machine install uv,
then run `uv sync --locked --all-groups` first. The ZIP intentionally excludes
the machine-specific `.venv` folder.

1. Choose `delay`, fixed detector, recovery off. Run the experiment.
2. Switch to aware detection. The valid pending procedure should avoid false alarms.
3. Choose `loss_ack`, seed 1. Compare recovery disabled and enabled.
4. Inspect the mismatched profiles, alarm and recovery events, then download JSON.
5. Show `observation_outage` or `recovery_failure` to explain why recovery can fail.

Run `run.ps1 test` to execute the 48 tests. Run `run.ps1 benchmark` for the
1,920-run suite and `run.ps1 sensitivity` for 720 additional runs.

## Evidence and scope

- `research/formal_model.md`: states, transitions, invariants and assumptions.
- `results/final-benchmark/runs.csv`: individual runs.
- `results/final-benchmark/summary.csv`: pooled results used in the deliverables.
- `results/final-benchmark/metadata.json`: parameters and source hashes.
- `results/sensitivity.csv`: held-out timing sensitivity experiments.
- `results/final-coverage.json`: recorded core coverage (98.9%).

This is a completed abstract simulation prototype. It does not implement full
handover, independent N4/UPF behavior or actual user-plane packet delivery. Reported
lead time is relative to consistency probes, and recovery success means state
convergence. The presentation and report explicitly preserve these boundaries.

The implementation review fixed source-hash collection when launched from another
folder and added a tested Windows launcher. Benchmarks were reproduced rather than
invented. The report was exported through Microsoft Word because LibreOffice was
unavailable, then all pages were visually inspected. Slides were rendered and
structurally validated, including editable chart data.

