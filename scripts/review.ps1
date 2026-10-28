<#
Prepare and open a safe, isolated Adaptive Watch review session on this machine (p022).

  powershell -ExecutionPolicy Bypass -File scripts\review.ps1            # start the isolated demo, open it in Edge and the film in Windows Media Player
  powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -Reset     # throw away this session's decisions and start again from the beginning
  powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -Stop      # stop only the review server
  powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -Film      # play the film only
  powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -ExportFilm  # copy the film to a folder for Remote Desktop file transfer
  powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -Notes     # open the private feedback notes file

The session lives entirely under runs\review. It uses its own copy of the railway case, its own native status and an
empty duplicate-send ledger. It never reads or writes the operator's saved state (runs\release\app), the review database
(runs\negative-result-review) or the server on port 8780. Native sending is off and no Hafnia password is asked for.
#>
param(
    [int]$Port = 8781,
    [switch]$Reset,
    [switch]$Stop,
    [switch]$Film,
    [switch]$ExportFilm,
    [switch]$Notes,
    [switch]$NoBrowser,
    [string]$Evaluations = "$env:USERPROFILE\adaptive-watch-private\hafnia-16"
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$reviewRoot = Join-Path $repo 'runs\review'
$sessionFile = Join-Path $reviewRoot 'session.json'
$filmPath = Join-Path $repo 'runs\release\adaptive-watch-submission.mp4'
$manifest = Get-Content (Join-Path $repo 'docs\submission\release-manifest.json') -Raw | ConvertFrom-Json
$notesDir = Join-Path $repo 'runs\review-notes'
$notesFile = Join-Path $notesDir 'product-owner-notes.txt'
$python = Join-Path $repo '.venv\Scripts\python.exe'

function Stop-Fail($message) { Write-Host "STOP: $message" -ForegroundColor Red; exit 1 }
function Test-PortBusy($p) { [bool](Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) }

function Open-Film {
    if (-not (Test-Path $filmPath)) { Stop-Fail "The film is missing: $filmPath" }
    $wmp = @("$env:ProgramFiles\Windows Media Player\wmplayer.exe", "${env:ProgramFiles(x86)}\Windows Media Player\wmplayer.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($wmp) { Start-Process $wmp -ArgumentList "`"$filmPath`"" } else { Start-Process $filmPath }
    Write-Host "Film: $filmPath"
}

function Open-App($p) {
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $edge) { Stop-Fail 'Microsoft Edge was not found.' }
    Start-Process $edge -ArgumentList '--new-window', "http://127.0.0.1:$p/#/railway"
}

# Returns the session record only if its process is alive AND its command line is this review server.
function Get-Session {
    if (-not (Test-Path $sessionFile)) { return $null }
    $s = Get-Content $sessionFile -Raw | ConvertFrom-Json
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($s.pid)" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -like '*adaptive_watch.app_api*' -and $proc.CommandLine -like "*$reviewRoot*") { return $s }
    return $null
}

function Stop-Session {
    $s = Get-Session
    if (-not $s) { Write-Host 'No review server is running.'; return }
    & taskkill.exe /PID $s.pid /T /F | Out-Null
    for ($i = 0; $i -lt 20 -and (Test-PortBusy $s.port); $i++) { Start-Sleep -Milliseconds 250 }
    if (Test-PortBusy $s.port) { Stop-Fail "Port $($s.port) is still busy after stopping the review server. Nothing else was touched." }
    Remove-Item $sessionFile -ErrorAction SilentlyContinue
    Write-Host "Review server stopped (port $($s.port) is free). Other Adaptive Watch servers were not touched."
}

if ($Notes) {
    New-Item -ItemType Directory -Force $notesDir | Out-Null
    if (-not (Test-Path $notesFile)) { Copy-Item (Join-Path $repo 'docs\submission\review-notes-template.txt') $notesFile }
    Start-Process notepad.exe -ArgumentList "`"$notesFile`""
    Write-Host "Notes (private, optional): $notesFile"
    exit 0
}
if ($Film) { Open-Film; exit 0 }
if ($ExportFilm) {
    $out = Join-Path $reviewRoot 'film-for-transfer'
    New-Item -ItemType Directory -Force $out | Out-Null
    $dest = Join-Path $out 'adaptive-watch-submission.mp4'
    Copy-Item $filmPath $dest -Force
    $hash = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $manifest.video.sha256) { Stop-Fail "The copy does not match the released film checksum ($hash)." }
    "$hash  adaptive-watch-submission.mp4" | Set-Content (Join-Path $out 'adaptive-watch-submission.mp4.sha256') -Encoding ascii
    Write-Host "Copy verified (SHA-256 $hash)."
    Write-Host "In the Remote Desktop window: select the file, Ctrl+C, then Ctrl+V on your own computer (clipboard file transfer or a redirected drive)."
    Write-Host "No network service is started and nothing is uploaded."
    Start-Process explorer.exe -ArgumentList "/select,`"$dest`""
    exit 0
}
if ($Stop) { Stop-Session; exit 0 }
if ($Reset) {
    Stop-Session
    if ((Test-Path $reviewRoot) -and ((Resolve-Path $reviewRoot).Path -ne (Join-Path (Resolve-Path (Join-Path $repo 'runs')).Path 'review'))) { Stop-Fail 'Refusing to reset: unexpected review folder.' }
    foreach ($sub in 'app', 'railway', 'release') {   # only this session's own folders; notes and the film export are kept
        $dir = Join-Path $reviewRoot $sub
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    }
    Write-Host 'Review session reset. Starting again from the beginning.'
}

# ---- 1. Source files and release build --------------------------------------------------------------------------
Write-Host 'Checking source files and the release build...'
if (-not (Test-Path $python)) { Stop-Fail 'Missing .venv. Run: uv sync' }
if (-not (Test-Path $Evaluations)) { Stop-Fail "Saved Hafnia responses not found at $Evaluations." }
foreach ($needed in 'runs\negative-result-review\review.sqlite3', 'runs\release\media\railway\original.mp4', 'runs\release\media\railway\media.json', 'runs\release\native\config.json', 'cameras.local.json') {
    if (-not (Test-Path (Join-Path $repo $needed))) { Stop-Fail "Missing source file: $needed" }
}
$deps = Join-Path $repo 'runs\tooling\pydeps'
if (-not (Test-Path (Join-Path $deps 'numpy'))) { Stop-Fail "Missing $deps (numpy, av, Pillow). Run the install step in scripts\launch.ps1 once." }
$dist = Join-Path $repo 'frontend\dist'
function Sha($f) { (Get-FileHash $f -Algorithm SHA256).Hash.ToLower() }
if (-not (Test-Path (Join-Path $dist 'index.html'))) { Stop-Fail 'frontend\dist is missing. Build it: cd frontend; bun run build' }
if ((Sha (Join-Path $dist 'index.html')) -ne $manifest.app.entrySha256) { Stop-Fail 'frontend\dist\index.html does not match the release manifest. Rebuild or restore the release build.' }
foreach ($asset in $manifest.app.assets.PSObject.Properties) {
    $f = Join-Path $dist "assets\$($asset.Name)"
    if (-not (Test-Path $f) -or (Sha $f) -ne $asset.Value) { Stop-Fail "Release build asset does not match the manifest: $($asset.Name)" }
}
if (-not (Test-Path $filmPath)) { Stop-Fail "The film is missing: $filmPath" }
if ((Sha $filmPath) -ne $manifest.video.sha256) { Stop-Fail 'The film does not match the released checksum.' }
Write-Host '  source files, release build and film: OK'

# ---- 2. Reuse a running session, else pick a free port ---------------------------------------------------------------
$running = Get-Session
if ($running) {
    Write-Host "The review server is already running on port $($running.port). Reopening it. Use -Reset to start from the beginning."
    if (-not $NoBrowser) { Open-App $running.port; Open-Film }
    Write-Host "Application: http://127.0.0.1:$($running.port)/#/railway"
    exit 0
}
if ($Port -in 8780, 8782) { Stop-Fail "Port $Port belongs to another Adaptive Watch instance. Use another port (default 8781)." }
$chosen = $Port
if (Test-PortBusy $chosen) {
    $busy = (Get-NetTCPConnection -State Listen -LocalPort $chosen | Select-Object -First 1).OwningProcess
    $chosen = (8783..8799) + (8800..8810) | Where-Object { -not (Test-PortBusy $_) } | Select-Object -First 1
    if (-not $chosen) { Stop-Fail 'No free port found between 8783 and 8810.' }
    Write-Host "  port $Port is in use (process $busy, left running); using $chosen instead"
}

# ---- 3. Isolated review root ---------------------------------------------------------------------------------------------
New-Item -ItemType Directory -Force $reviewRoot | Out-Null
$app = Join-Path $reviewRoot 'app'
$railway = Join-Path $reviewRoot 'railway'
$release = Join-Path $reviewRoot 'release'
$env:PYTHONPATH = "$repo;$deps"
& $python 'scripts\adaptive_watch\make_demo_root.py' --target $railway | Out-Null
if ($LASTEXITCODE) { Stop-Fail 'Could not prepare the isolated railway case.' }
New-Item -ItemType Directory -Force (Join-Path $release 'media\railway'), (Join-Path $release 'native'), $app | Out-Null
Copy-Item (Join-Path $repo 'runs\release\media\railway\*') (Join-Path $release 'media\railway') -Force
Copy-Item (Join-Path $repo 'runs\release\native\config.json') (Join-Path $release 'native\config.json') -Force
& $python 'scripts\adaptive_watch\record_agent_review.py' --root $app --railway $railway --release $release --evaluations $Evaluations | Out-Null
if ($LASTEXITCODE) { Stop-Fail 'Could not prepare the isolated review state.' }

# ---- 4. Start the server (no --native-send, no --gateway-prompt) ------------------------------------------------------------
$serverArgs = @('-m', 'adaptive_watch.app_api', '--evaluations', $Evaluations, '--port', $chosen, '--root', $app, '--railway', $railway,
          '--release', $release, '--event-target', '127.0.0.1:9090')   # no --native-send: the server refuses to send
$proc = Start-Process $python -ArgumentList $serverArgs -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $reviewRoot 'server.log') -RedirectStandardError (Join-Path $reviewRoot 'server.err')
@{ pid = $proc.Id; port = $chosen; startedAt = (Get-Date).ToString('s'); root = $reviewRoot } | ConvertTo-Json | Set-Content $sessionFile

$base = "http://127.0.0.1:$chosen"
$ready = $false
for ($i = 0; $i -lt 40 -and -not $ready; $i++) {
    Start-Sleep -Milliseconds 500
    try { $ready = (Invoke-RestMethod "$base/api/health" -Headers @{ Origin = $base }).ok } catch {}
}
if (-not $ready) { Stop-Session; Stop-Fail "The review server did not start. See $reviewRoot\server.err" }

# ---- 5. Confirm every case loads and its source files verify --------------------------------------------------------------
$h = @{ Origin = $base }
foreach ($id in 'railway', 'gate', 'scooter', 'bin') {
    try { $case = (Invoke-RestMethod "$base/api/cases/$id" -Headers $h).case } catch { Stop-Session; Stop-Fail "Case '$id' did not load or failed source verification: $($_.Exception.Message)" }
    if ($id -eq 'railway' -and $case.state.status -ne 'review_required') { Stop-Session; Stop-Fail 'The railway case is not in its starting state.' }
}
try {
    $video = Invoke-WebRequest "$base/api/cases/railway/video" -Headers @{ Origin = $base } -UseBasicParsing
    if ($video.StatusCode -ne 200 -or $video.RawContentLength -lt 100000) { throw 'unexpected response' }
} catch { Stop-Session; Stop-Fail "The railway video did not load: $($_.Exception.Message)" }
Write-Host "  all four cases load and verify; native sending: off; Hafnia password: not needed"

Write-Host ''
Write-Host "Application: $base/#/railway   (isolated session in runs\review; port $chosen)"
Write-Host "Film:        $filmPath"
Write-Host 'Switch between the film and the application with Alt+Tab. Stop: scripts\review.ps1 -Stop   Start over: scripts\review.ps1 -Reset'
if (-not $NoBrowser) { Open-App $chosen; Open-Film }



