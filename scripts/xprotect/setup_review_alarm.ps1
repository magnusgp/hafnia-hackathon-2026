# Idempotent setup of the Adaptive Watch review event and one camera-specific alarm definition.
# Run only with explicit approval: it changes XProtect configuration (creates, never edits or deletes).
# Sends no event and raises no alarm.
param([string]$CameraName = 'person_on_railway_tracks',
      [string]$EventName = 'Adaptive Watch Review Required',
      [string]$AlarmName = 'Adaptive Watch review: station platform')
$ErrorActionPreference = 'Stop'
Import-Module MilestonePSTools
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula | Out-Null
$folder = Get-ConfigurationItem -Path '/AnalyticsEventFolder'
if (-not ($folder.Children | Where-Object DisplayName -eq $EventName)) {
    $m = $folder | Invoke-Method -MethodId AddAnalyticsEvent
    $m | Set-ConfigurationItemProperty -Key Name -Value $EventName
    $m | Set-ConfigurationItemProperty -Key Description -Value 'Hafnia returned a negative assessment and independent local vision flagged the same camera. A person should review the footage. Not a confirmed incident.'
    $null = $m | Invoke-Method -MethodId AddAnalyticsEvent
}
$existing = Get-VmsAlarmDefinition | Where-Object Name -eq $AlarmName
if (-not $existing) {
    $cam = Get-VmsCamera -Name $CameraName
    $probe = Get-VmsAlarmDefinition | Select-Object -First 1
    $eventId = $probe.EventTypeValues[$EventName]
    $groupId = $probe.EventTypeGroupValues['Analytics Events']
    $null = New-VmsAlarmDefinition -Name $AlarmName -EventTypeGroup $groupId -EventType $eventId -Source $cam.Path -RelatedCameras $cam -Priority 'Medium' `
        -Instructions 'Hafnia answered no entry; independent vision flagged this camera. Review the footage. This is a review exception, not confirmed trespass.'
}
Get-VmsAlarmDefinition | Where-Object Name -eq $AlarmName | Select-Object Name, Enabled, SourceList, EventType, Id | Format-List
