param([ValidateSet('app','test','demo','benchmark','sensitivity')][string]$Task = 'app')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        throw 'Project environment missing. Run uv sync --locked --all-groups first.'
    }
    switch ($Task) {
        'app' { & $projectPython -m streamlit run app.py }
        'test' { & $projectPython -m pytest -q }
        'demo' { & $projectPython -m ue_context.cli demo --config configs/demo.yaml }
        'benchmark' { & $projectPython -m ue_context.cli benchmark --trials 40 --out results/final-benchmark }
        'sensitivity' { & $projectPython -m scripts.sensitivity }
    }
    if ($LASTEXITCODE -ne 0) { throw "Project command failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
