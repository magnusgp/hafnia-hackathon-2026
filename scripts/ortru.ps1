# Start Ortru on p022: http://127.0.0.1:8790 (loopback only; open it inside p022).
#
#   scripts\ortru.ps1                 start (reads XProtect, runs local vision; the Hafnia step waits for a gateway sign-in)
#   scripts\ortru.ps1 -Gateway        also ask once, in a new window, for the Hafnia gateway password (kept in memory only)
#   scripts\ortru.ps1 -NativeSend     allow one confirmed review event at a time to be sent to the XProtect Event Server
#   scripts\ortru.ps1 -Prepare        rebuild the private evidence archive copy first (read only against the operator state)
#   scripts\ortru.ps1 -Gateway -NativeSend   the operational start: both. If Ortru already runs without them, only that instance restarts
#                                     (the plan is printed first; stored work is kept; a running sign-in or sending is never dropped unless -Restart)
#   scripts\ortru.ps1 -Restart        restart only the Ortru instance
#   scripts\ortru.ps1 -Stop         stop the Ortru server (by its own process; other servers are not touched)
#
# Ortru keeps its own state in runs\ortru and never writes to the operator's earlier state (runs\release\app, review
# databases). The only shared file it appends to is the duplicate-send ledger, and only for a confirmed native send.
param(
    [int]$Port = 8790,
    [switch]$Gateway, [switch]$NativeSend, [switch]$Prepare, [switch]$Stop, [switch]$Restart, [switch]$NoBrowser,
    [string]$Data = '',     # checkout that holds the private runs\ data and tooling (default: this checkout, else the main checkout)
    [string]$Evaluations = "$env:USERPROFILE\adaptive-watch-private\hafnia-16"
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
if (-not $Data) {
    $Data = if (Test-Path (Join-Path $repo '.venv\Scripts\python.exe')) { $repo } else { 'C:\Users\Administrator\dev\hafnia-hackathon-2026' }
}
$python = Join-Path $Data '.venv\Scripts\python.exe'
$root = Join-Path $repo 'runs\ortru'
if ($Port -in 8770, 8771, 8776, 8778, 8780, 8781, 8782) { throw "Port $Port belongs to another Adaptive Watch instance. Use a different port." }

function Find-Server { Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ortru\.server' -and $_.CommandLine -match "--port $Port\b" } }

function Stop-Ortru {
    # Only the process tree whose command line is ortru.server on this port. Nothing else is touched.
    $all = @(Find-Server)
    if (-not $all) { return $false }
    $top = $all | Where-Object { $pp = $_.ParentProcessId; -not ($all | Where-Object { $_.ProcessId -eq $pp }) } | Select-Object -First 1
    & taskkill /PID $top.ProcessId /T /F | Out-Null
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is still in use." }
    return $true
}

if ($Stop) {
    if (Stop-Ortru) { Write-Host "Ortru stopped (port $Port)." } else { Write-Host "No Ortru server is running on port $Port." }
    return
}

if (Find-Server) {
    $url = "http://127.0.0.1:$Port"
    $state = $null
    try { $state = (Invoke-RestMethod "$url/api/ortru" -TimeoutSec 10).data } catch { }
    $hasGateway = [bool]($state -and $state.gateway.available)
    $hasSend = [bool]($state -and $state.native.sending)
    $change = @()
    if ($Gateway -and -not $hasGateway) { $change += 'Hafnia gateway sign-in (you type the password in the new window; it is kept in memory only)' }
    if ($NativeSend -and -not $hasSend) { $change += 'XProtect sending enabled (each event still needs your explicit confirmation)' }
    if (-not $Restart -and -not $change) {
        Write-Host "Ortru is already running on $url with Hafnia sign-in $(if ($hasGateway) { 'active' } else { 'not active' }) and XProtect sending $(if ($hasSend) { 'on' } else { 'off' }). Nothing to change."
        if (-not $NoBrowser) { Start-Process 'msedge.exe' "$url/" }
        return
    }
    Write-Host "Ortru is already running on $url without what you asked for. Restarting only this Ortru instance (port $Port):"
    if ($change) { $change | ForEach-Object { Write-Host "  + $_" } } else { Write-Host '  (plain restart)' }
    if ($hasGateway -and -not $Gateway) { Write-Host '  - The current Hafnia sign-in is lost; add -Gateway to sign in again.' }
    if ($hasSend -and -not $NativeSend) { Write-Host '  - XProtect sending turns off; add -NativeSend to keep it.' }
    Write-Host '  Kept: Watches, assessments, exceptions, decisions and the send ledger (all stored on disk). Unfinished assessments resume on start.'
    Write-Host '  Not touched: XProtect, the Hafnia gateway, GPU processes, other servers.'
    [void](Stop-Ortru)
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is already in use by another program. Use -Port." }
if (-not (Test-Path (Join-Path $repo 'frontend\dist\index.html'))) { throw 'The interface is not built. Run: cd frontend; bun run build' }
New-Item -ItemType Directory -Force $root | Out-Null
if ($Prepare -or -not (Test-Path (Join-Path $root 'archive\app\workspace.sqlite3'))) {
    & $python (Join-Path $repo 'scripts\ortru_prepare.py') --source $Data --target $root
}
$serverArgs = @('-m', 'ortru.server', '--port', $Port, '--root', $root, '--archive', (Join-Path $root 'archive'), '--data-repo', $Data, '--evaluations', $Evaluations)
if ($NativeSend) { $serverArgs += '--native-send' }
$env:PYTHONPATH = $repo
if ($Gateway) {
    $serverArgs += '--gateway-prompt'
    Start-Process $python -ArgumentList $serverArgs -WorkingDirectory $repo   # visible window: the password is typed there, never in the browser
} else {
    $log = Join-Path $root 'server.log'
    Start-Process $python -ArgumentList $serverArgs -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError ($log + '.err')
}
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest "http://127.0.0.1:$Port/api/ortru" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 700 }
}
try { Invoke-WebRequest "http://127.0.0.1:$Port/api/ortru" -UseBasicParsing -TimeoutSec 5 | Out-Null } catch {
    if ($Gateway) { Write-Host 'Enter the Hafnia gateway password in the new window, then open http://127.0.0.1:' $Port; return }
    throw 'Ortru did not start. See runs\ortru\server.log.err'
}
Write-Host "Ortru: http://127.0.0.1:$Port$(if ($NativeSend) { '  (XProtect sending ON)' } else { '  (XProtect sending off)' })"
if (-not $NoBrowser) { Start-Process 'msedge.exe' "http://127.0.0.1:$Port/" }
