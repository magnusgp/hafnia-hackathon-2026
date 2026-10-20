# Run in Windows PowerShell on the hackathon VM (MilestonePSTools preinstalled).
$ErrorActionPreference = 'Stop'
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula
Get-VmsCamera | Select-Object Name, Id | Format-Table -AutoSize
# Optional name-based CLI catalog; local file is ignored by Git:
# Get-VmsCamera | Select-Object Name, Id | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 cameras.local.json
