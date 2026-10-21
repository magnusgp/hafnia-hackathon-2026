# Read-only except for IDP token acquisition. No event writes or VM configuration changes.
# Dot-source this script to retain the bearer token in this PowerShell process only.
param([switch]$BasicUser)
$ErrorActionPreference = 'Stop'
$origin = 'https://p022'
$env:XPROTECT_URL = $origin
try {
    # Windows certificate validation remains enabled. Stop here on a trust/hostname failure.
    $null = Invoke-RestMethod "$origin/api/.well-known/uris" -Method Get -TimeoutSec 20 -MaximumRedirection 0
    Write-Host 'TLS and API discovery: OK'
    $null = Invoke-RestMethod "$origin/IDP/.well-known/openid-configuration" -Method Get -TimeoutSec 20 -MaximumRedirection 0
    Write-Host 'IDP discovery: OK'
    if ($BasicUser) {
        $credential = Get-Credential -Message 'Existing authorized XProtect Basic user (no account changes)'
        $body = @{grant_type='password'; client_id='GrantValidatorClient'; username=$credential.UserName; password=$credential.GetNetworkCredential().Password}
        $response = Invoke-RestMethod "$origin/API/IDP/connect/token" -Method Post -TimeoutSec 20 -MaximumRedirection 0 -ContentType 'application/x-www-form-urlencoded' -Body $body
        $body.password = $null
        $credential = $null
    } else {
        # Official Events REST quickstart: windows_credentials with Windows/NTLM authentication.
        $body = @{grant_type='windows_credentials'; client_id='GrantValidatorClient'}
        $response = Invoke-RestMethod "$origin/API/IDP/connect/token" -Method Post -TimeoutSec 20 -MaximumRedirection 0 -ContentType 'application/x-www-form-urlencoded' -Body $body -UseDefaultCredentials
    }
    if (-not $response.access_token) { throw 'No token' }
    $env:XPROTECT_TOKEN = $response.access_token
    $response = $null
    $headers = @{Authorization="Bearer $env:XPROTECT_TOKEN"}
    $types = Invoke-RestMethod "$origin/api/rest/v1/eventTypes?size=200" -Headers $headers -Method Get -TimeoutSec 20 -MaximumRedirection 0
    $cameras = Invoke-RestMethod "$origin/api/rest/v1/cameras?size=200" -Headers $headers -Method Get -TimeoutSec 20 -MaximumRedirection 0
    # Local candidate inventory only. Pagination must be resolved before selecting a write target.
    @{eventTypes=$types; cameras=$cameras} | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 xprotect-candidates.local.json
    Write-Host 'Token acquired in memory; read-only event-type/camera candidate inventory saved locally.'
    Write-Host 'STOP: no write is implemented. Verify type/source, deployed schema and downstream alarm definition before requesting an event write.'
} catch {
    Remove-Item Env:XPROTECT_TOKEN -ErrorAction SilentlyContinue
    # Do not echo server bodies, credential objects, bearer headers or exception details.
    Write-Host 'REST preflight failed. Check TLS trust, IDP path and Windows/Basic-user permissions locally. No settings were changed.'
} finally {
    $credential = $null
    $response = $null
    $headers = $null
    if ($body) { $body.password = $null }
    $body = $null
}
