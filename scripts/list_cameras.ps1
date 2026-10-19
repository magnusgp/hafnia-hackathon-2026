# Run in Windows PowerShell on the hackathon VM (MilestonePSTools preinstalled).
$ErrorActionPreference = 'Stop'
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula
Get-VmsCamera | Select-Object Name, Id | Format-Table -AutoSize
