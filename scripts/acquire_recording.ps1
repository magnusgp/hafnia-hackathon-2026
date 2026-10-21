# Read-only acquisition of a short RECORDED interval from one existing camera.
# Uses MilestonePSTools (preinstalled): Get-SequenceData, Get-Snapshot (recorded JPEGs) and,
# with -Mkv, Start-Export -Format MKV. No VMS configuration, recording, service, firewall,
# evidence-lock or VLM changes. Output goes to the git-ignored runs\xprotect\ folder.
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\acquire_recording.ps1 -CameraName vandalism
#   powershell -ExecutionPolicy Bypass -File .\scripts\acquire_recording.ps1 -CameraName vandalism -Start '2026-10-21T12:00:00Z' -Seconds 10 -Mkv
param(
    [Parameter(Mandatory = $true)][string]$CameraName,
    [string]$Start,                  # UTC, e.g. 2026-10-21T12:00:00Z. Default: end of the latest recording minus a margin
    [ValidateRange(2, 60)][int]$Seconds = 10,
    [ValidateRange(0.1, 10)][double]$Interval = 0.5,
    [switch]$Mkv,
    [string]$OutRoot = 'runs\xprotect'
)
$ErrorActionPreference = 'Stop'
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula | Out-Null
$pstools = (Get-Module MilestonePSTools).Version.ToString()

# Exact, case-sensitive, unique camera name; never pick one of several.
$cams = @(Get-VmsCamera -Name $CameraName | Where-Object { $_.Name -ceq $CameraName })
if ($cams.Count -ne 1) { throw "Camera name '$CameraName' resolved to $($cams.Count) cameras; need exactly one." }
$cam = $cams[0]

function AsUtc([DateTime]$t) {
    # MIP SDK reports UTC; an Unspecified kind is taken as UTC (recorded in the manifest), never as local.
    if ($t.Kind -eq [DateTimeKind]::Local) { return $t.ToUniversalTime() }
    return [DateTime]::SpecifyKind($t, [DateTimeKind]::Utc)
}
function Iso([DateTime]$t) { return $t.ToString("yyyy-MM-ddTHH:mm:ss.fffZ") }

$nowUtc = [DateTime]::UtcNow
$seqs = @($cam | Get-SequenceData -SequenceType RecordingSequence -StartTime $nowUtc.AddHours(-6) -EndTime $nowUtc -CropToTimeSpan)
Write-Host "Recording sequences in the last 6 h: $($seqs.Count)"
$seqs | Select-Object -Last 5 | ForEach-Object {
    Write-Host ('  ' + (Iso (AsUtc $_.EventSequence.StartDateTime)) + ' -> ' + (Iso (AsUtc $_.EventSequence.EndDateTime)))
}
if ($Start) {
    $startUtc = [DateTime]::Parse($Start, [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
} else {
    if ($seqs.Count -eq 0) { throw 'No recording sequence found in the last 6 h; pass -Start explicitly.' }
    $last = $seqs[-1].EventSequence
    $startUtc = (AsUtc $last.EndDateTime).AddSeconds(-($Seconds + 30))
    if ($startUtc -lt (AsUtc $last.StartDateTime)) { throw 'Latest recording sequence is shorter than the requested interval; pass -Start.' }
}
$startUtc = [DateTime]::SpecifyKind($startUtc, [DateTimeKind]::Utc)
$endUtc = $startUtc.AddSeconds($Seconds)
$covered = @($seqs | Where-Object { (AsUtc $_.EventSequence.StartDateTime) -le $startUtc -and (AsUtc $_.EventSequence.EndDateTime) -ge $endUtc })
Write-Host "Requested: $(Iso $startUtc) -> $(Iso $endUtc)  (inside one recording sequence: $($covered.Count -gt 0))"

$dir = Join-Path $OutRoot ($CameraName + '_' + $startUtc.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# Recorded JPEGs. Bytes are written by this script so file names and timestamps are explicit.
$sw = [Diagnostics.Stopwatch]::StartNew()
$snaps = @($cam | Get-Snapshot -Timestamp $startUtc -EndTime $endUtc -Interval $Interval)
$sw.Stop()
if ($snaps.Count -eq 0) { throw 'Get-Snapshot returned no frames for this interval.' }
$first = $snaps[0]
if (-not ($first.PSObject.Properties.Name -contains 'DateTime') -or -not ($first.PSObject.Properties.Name -contains 'Bytes')) {
    Write-Host 'UNEXPECTED snapshot object. Properties:'
    $first | Get-Member -MemberType Property | Format-Table Name, Definition -AutoSize | Out-String | Write-Host
    throw 'Report these properties; the manifest writer expects DateTime and Bytes.'
}
$frames = @()
$i = 0
foreach ($s in $snaps) {
    $name = 'frame_{0:D4}.jpg' -f $i
    [IO.File]::WriteAllBytes((Join-Path (Resolve-Path $dir) $name), $s.Bytes)
    $frames += [ordered]@{ file = $name; timestamp_utc = (Iso (AsUtc $s.DateTime)); bytes = $s.Bytes.Length }
    $i++
}
$manifest = [ordered]@{
    source = 'Get-Snapshot'; camera_name = $cam.Name; camera_id = $cam.Id.ToString()
    requested_start_utc = (Iso $startUtc); requested_end_utc = (Iso $endUtc); interval_s = $Interval
    elapsed_s = $sw.Elapsed.TotalSeconds; pstools_version = $pstools
    timestamp_kind_reported = $first.DateTime.Kind.ToString(); frames = $frames
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $dir 'manifest.json')
Write-Host ("Get-Snapshot: {0} frames in {1:N2} s ({2:N1} ms/frame). First {3}, last {4}. Kind reported: {5}" -f
    $frames.Count, $sw.Elapsed.TotalSeconds, (1000 * $sw.Elapsed.TotalSeconds / $frames.Count),
    $frames[0].timestamp_utc, $frames[-1].timestamp_utc, $first.DateTime.Kind)
Write-Host "Next: uv run --group ml python aw.py footage --manifest $dir\manifest.json --save"

if ($Mkv) {
    # Server-side export without transcoding. Writes a local file only; no evidence lock.
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Export -CameraIds $cam.Id -Format MKV -StartTime $startUtc -EndTime $endUtc -Path (Resolve-Path $dir) -Name 'clip' | Out-Null
    $sw.Stop()
    $file = Get-ChildItem -Path $dir -Recurse -Filter *.mkv | Select-Object -First 1
    if (-not $file) { throw 'Start-Export finished but no .mkv was found in the output folder.' }
    Write-Host ("MKV export: {0} ({1:N0} KB) in {2:N2} s" -f $file.FullName, ($file.Length / 1KB), $sw.Elapsed.TotalSeconds)
    Write-Host "Next: uv run --group ml python aw.py footage --mkv `"$($file.FullName)`" --start $(Iso $startUtc) --sample-fps 2 --acquisition-s $([Math]::Round($sw.Elapsed.TotalSeconds, 2)) --save"
}
