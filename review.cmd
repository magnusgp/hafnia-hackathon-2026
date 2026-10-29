@powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review.ps1" %*
@if errorlevel 1 pause
