# Operator-authorized REL26-B batch. Credentials stay in this terminal.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo
$python = Join-Path $repo '.venv/Scripts/python.exe'
$runner = Join-Path $PSScriptRoot 'reliability_runner.py'
$batchArgs = @('--root', 'runs/reliability-fresh/operator-batch',
    '--plan', 'runs/reliability-fresh/execution-plan.private.json',
    '--review', 'runs/reliability-fresh/fresh-signoff.private.json',
    '--operator-auth-confirmed')
& $python $runner @batchArgs --authenticated-preflight
if ($LASTEXITCODE -ne 0) { throw 'Authentication preflight failed; no submissions attempted.' }
& (Join-Path $PSScriptRoot 'reliability_availability.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Recording coverage refresh failed; no submissions attempted.' }
Write-Host 'Preflight completed. Enter the password again for the authorized four-request execution.'
& $python $runner @batchArgs --apply --quota-contract docs/research/reliability/quota-contract.json --recording-availability runs/reliability-fresh/recording-availability.private.json
if ($LASTEXITCODE -ne 0) { throw 'Execution stopped. Preserve the ledger; reconcile any ambiguous submission before continuing.' }
