# Start Adaptive Watch on this machine and open it in Edge. Run inside p022 (localhost is local to it).
#
#   powershell -ExecutionPolicy Bypass -File scripts\launch.ps1 -Demo              # judge walkthrough, nothing saved yet
#   powershell -ExecutionPolicy Bypass -File scripts\launch.ps1                    # the operator's real saved state
#   powershell -ExecutionPolicy Bypass -File scripts\launch.ps1 -AssessmentLogin   # also enables New assessment
#
# -Demo opens an isolated copy of the flagship case in its pending state, so the whole flow can be walked through
# without touching the operator's saved decision.
# -AssessmentLogin asks once, in this window, for the Hafnia gateway password. It is held in the server's memory
# only. It never reaches the browser, a file or a log. Without it, saved cases work and New assessment explains why
# it is unavailable.
# -NativeSend allows the server to send one reviewed event to the XProtect Event Server after a confirmation in the
# browser. Without it the send step shows a preview only.
param(
    [int]$Port = 8780,
    [string]$Evaluations = "$env:USERPROFILE\adaptive-watch-private\hafnia-16",
    [switch]$Demo,
    [switch]$AssessmentLogin,
    [switch]$NativeSend,
    [string]$EventTarget = '127.0.0.1:9090',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Missing .venv. Run: uv sync' }
if (-not (Test-Path (Join-Path $repo 'frontend\dist\index.html'))) {
    $bun = Join-Path $repo 'runs\tooling\bun-windows-x64\bun.exe'
    if (-not (Test-Path $bun)) { $bun = (Get-Command bun -ErrorAction Stop).Source }
    Push-Location (Join-Path $repo 'frontend'); & $bun install; & $bun run build; Pop-Location
}
if (-not (Test-Path $Evaluations)) { Write-Warning "Saved Hafnia responses not found at $Evaluations. Cases that need them will be withheld." }
$env:PYTHONPATH = $repo
$serverArgs = @('-m', 'adaptive_watch.app_api', '--evaluations', $Evaluations, '--port', $Port, '--event-target', $EventTarget)
if ($Demo) {
    & $python 'scripts\adaptive_watch\make_demo_root.py' | Out-Null
    & $python 'scripts\adaptive_watch\record_agent_review.py' --root 'runs\release\demo-app' --railway 'runs\release\demo-railway' --evaluations $Evaluations | Out-Null
    $serverArgs += @('--root', 'runs\release\demo-app', '--railway', 'runs\release\demo-railway')
}
if ($AssessmentLogin) { $serverArgs += '--gateway-prompt' }
if ($NativeSend) { $serverArgs += '--native-send' }
if (-not $NoBrowser) {
    Start-Job -ScriptBlock { param($p) Start-Sleep 3; Start-Process msedge "http://127.0.0.1:$p/#/railway" } -ArgumentList $Port | Out-Null
}
Write-Host "Adaptive Watch: http://127.0.0.1:$Port  (close this window to stop)"
& $python @serverArgs
