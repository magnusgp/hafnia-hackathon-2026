# Interactive authentication preflight only. Never submits inference summaries.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv/Scripts/python.exe'
$runner = Join-Path $PSScriptRoot 'reliability_runner.py'
& $python $runner --root (Join-Path $repo 'runs/reliability-fresh/operator-batch') `
    --plan (Join-Path $repo 'runs/reliability-fresh/execution-plan.private.json') `
    --review (Join-Path $repo 'runs/reliability-fresh/fresh-signoff.private.json') `
    --authenticated-preflight --operator-auth-confirmed
if ($LASTEXITCODE -ne 0) { throw 'Authenticated preflight did not pass; no inference was submitted.' }
