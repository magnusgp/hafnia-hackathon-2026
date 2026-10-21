# Run in the checkout on p022. Credentials stay in this process and its child.
param([switch]$Offline, [int]$Port = 8086)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
$previousPassword = $env:HAFNIA_GW_PASSWORD
try {
    if (-not $Offline -and -not $env:HAFNIA_GW_PASSWORD) {
        $secret = Read-Host 'Local Hafnia gateway administrator password' -AsSecureString
        $env:HAFNIA_GW_PASSWORD = [Net.NetworkCredential]::new('', $secret).Password
        $secret = $null
    }
    uv run --frozen python scene_web.py --port $Port
} finally {
    $env:HAFNIA_GW_PASSWORD = $previousPassword
    Pop-Location
}
