# Exactly the authorized REL26-D matrix. One interactive login; no saved credentials.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo
try {
    & (Join-Path $PSScriptRoot 'reliability_availability.ps1') -EvaluationRoot runs/reliability-diagnostics -PlanPath runs/reliability-diagnostics/execution-plan-v1.private.json
} catch {
    throw ('Coverage refresh failed; no inference attempted. ' + $_.Exception.Message)
}
& (Join-Path $repo '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'reliability_diagnostic_execute.py')
if ($LASTEXITCODE -ne 0) { throw 'Campaign stopped. Preserve ledger; reconcile ambiguous claims, never retry them.' }
