# Read-only recording coverage refresh. No inference or VMS configuration changes.
param([string]$EvaluationRoot, [string]$PlanPath)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $EvaluationRoot) { $EvaluationRoot = Join-Path $repo 'runs/reliability-fresh' }
if (-not $PlanPath) { $PlanPath = Join-Path $EvaluationRoot 'execution-plan.private.json' }
$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
Import-Module MilestonePSTools
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula | Out-Null
$checked = [DateTime]::UtcNow
$records = @()
foreach ($entry in ($plan | Group-Object source_recording_id | ForEach-Object { $_.Group[0] })) {
    $cameraName = if ($entry.camera_name) { $entry.camera_name } elseif ($entry.recording_manifest) {
        (Get-Content -LiteralPath $entry.recording_manifest -Raw | ConvertFrom-Json).camera_name
    } else { $entry.scene }
    $cams = @(Get-VmsCamera -Name $cameraName | Where-Object { $_.Name -ceq $cameraName -and $_.Id.ToString() -ieq $entry.camera_id })
    if ($cams.Count -ne 1) { throw 'Exact source camera is unavailable' }
    $start = [DateTime]::Parse($entry.start).ToUniversalTime()
    $end = [DateTime]::Parse($entry.end).ToUniversalTime()
    if ($start -le $checked.AddHours(-24) -or $end -gt $checked) { throw 'Recording age is invalid' }
    $sequences = @($cams[0] | Get-SequenceData -SequenceType RecordingSequence -StartTime $checked.AddHours(-24) -EndTime $checked -CropToTimeSpan)
    $coverage = @($sequences | ForEach-Object {
        [ordered]@{ start_utc = [DateTime]::SpecifyKind($_.EventSequence.StartDateTime,[DateTimeKind]::Utc).ToString('o')
                    end_utc = [DateTime]::SpecifyKind($_.EventSequence.EndDateTime,[DateTimeKind]::Utc).ToString('o') }
    } | Where-Object { [DateTime]::Parse($_.start_utc).ToUniversalTime() -le $start -and [DateTime]::Parse($_.end_utc).ToUniversalTime() -ge $end })
    if ($coverage.Count -eq 0) { throw 'No recording sequence covers the exact interval' }
    $proof = Join-Path $evaluationRoot ($entry.scene + '-coverage-' + $checked.ToString('yyyyMMddTHHmmssfffZ') + '.private.json')
    [ordered]@{ camera_id=$entry.camera_id; source_recording_id=$entry.source_recording_id; checked_at=$checked.ToString('o'); recording_sequences=$coverage } |
        ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $proof
    $records += [ordered]@{ event_id=$entry.event_id; manifest_sha256=$entry.manifest_sha256; available=$true
        checked_by='Existing Windows VMS session; read-only Get-SequenceData'; checked_at=$checked.ToString('o')
        coverage_start=$coverage[0].start_utc; coverage_end=$coverage[0].end_utc
        evidence_file=$proof; evidence_sha256=(Get-FileHash -LiteralPath $proof -Algorithm SHA256).Hash.ToLower() }
}
@{recordings=$records} | ConvertTo-Json -Depth 7 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $evaluationRoot 'recording-availability.private.json')
Write-Host ('Verified exact recording coverage for ' + $records.Count + ' sources; zero inference calls')
