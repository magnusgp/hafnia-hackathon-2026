# Render narration.json to one WAV per scene with the local Windows speech engine (no network, no cloud voice).
param([string]$Json = "$PSScriptRoot\narration.json", [string]$Out = "$PSScriptRoot\assets\audio", [int]$Rate = -1)
Add-Type -AssemblyName System.Speech
$spec = Get-Content $Json -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force $Out | Out-Null
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($spec.voice); $s.Rate = $Rate
foreach ($scene in $spec.scenes) {
    $s.SetOutputToWaveFile("$Out\$($scene.id).wav")
    $s.Speak($scene.text)
    $s.SetOutputToNull()
}
$s.Dispose()
Get-ChildItem $Out -Filter *.wav | ForEach-Object { "{0} {1:N1} KB" -f $_.Name, ($_.Length/1KB) }
