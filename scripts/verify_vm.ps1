# Read-only preflight for the hackathon VM. Does not modify services, credentials or firewall.
$ErrorActionPreference = 'Continue'
Write-Host ('Host: ' + $env:COMPUTERNAME)
Write-Host ('Python: ' + (py --version 2>&1))
Get-Service | Where-Object {$_.DisplayName -like '*Recording Server*' -or $_.Name -eq 'Hafnia.Vlm.Gateway'} | Select-Object DisplayName,Status | Format-Table -AutoSize
try {
    $health = & curl.exe -k -sS -o NUL -w '%{http_code}' 'https://localhost:15443/api/System/Information'
    Write-Host ('Local Hafnia gateway system endpoint HTTP: ' + $health)
} catch { Write-Warning 'Gateway health request failed' }
