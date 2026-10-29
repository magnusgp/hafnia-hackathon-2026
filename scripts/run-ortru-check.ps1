# Starts a fresh isolated Ortru fixture server (fake effects, test transport) and runs the browser acceptance check against it.
# Usage: powershell -File scripts\run-ortru-check.ps1 [-Data <checkout with runs/>] [-Port 8795]
param([string]$Data = 'C:\Users\Administrator\dev\hafnia-hackathon-2026', [int]$Port = 8795, [string]$Out = 'runs\ortru\shots')
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
$py = Join-Path $Data '.venv\Scripts\python.exe'
$bun = Join-Path $Data 'runs\tooling\bun-windows-x64\bun.exe'
$old = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "tests.ortru_fixture --port $Port" -and $_.Name -match 'python' }
foreach ($p in $old) { & taskkill /PID $p.ProcessId /T /F | Out-Null }
$log = Join-Path $repo 'runs\ortru\fixture.log'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$proc = Start-Process $py -ArgumentList @('-m', 'tests.ortru_fixture', '--port', $Port, '--archive', 'runs\ortru\archive', '--data-repo', $Data, '--video', (Join-Path $Data 'runs\release\media\railway\original.mp4')) -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError ($log + '.err') -PassThru
for ($i = 0; $i -lt 40; $i++) { try { Invoke-WebRequest "http://127.0.0.1:$Port/api/ortru" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }
Set-Location (Join-Path $repo 'frontend')
& $bun scripts/check-ortru.mjs (Join-Path $repo $Out) "http://127.0.0.1:$Port"
$code = $LASTEXITCODE
foreach ($p in (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "tests.ortru_fixture --port $Port" })) { & taskkill /PID $p.ProcessId /T /F | Out-Null }
exit $code
