# Adaptive Watch

Adaptive Watch opens at `/` as an evidence-verification workspace with four source-verified saved assessments: railway, school gate, scooter and bin. Each preserves its original camera and recording interval. Prompt variants and repeated scene loops are not independent events.

The Polar railway investigation, original footage, region editor and review controls are preserved. Scooter and bin use their own timestamped snapshots and CV stationarity measurements. Gate shows original negative conclusions and separately dated prompt diagnostics, without invented CV.

**Fresh browser analysis remains blocked.** New assessment offers only the two cameras supported by the existing persistent-object backend. It validates a past 12-17 second UTC interval within 24 hours, then reports the missing authenticated runtime, CUDA transport and acquisition/continuity handoff. No acquisition or Hafnia request is submitted. This is not a completed end-to-end analysis application.

## Build and open on p022

Run from the repository root:

```powershell
cd frontend
..\runs\tooling\bun-windows-x64\bun.exe run build
cd ..
.\.venv\Scripts\python.exe -m adaptive_watch.workspace_api --root runs/application --railway runs/negative-result-review --evaluations C:/Users/Administrator/adaptive-watch-private/hafnia-16 --frontend frontend/dist --port 8777
```

Open http://127.0.0.1:8777 **inside p022**, using existing authorized desktop access. A localhost address on another computer does not reach p022. The foreground launch stops when its terminal closes. No service, VMS configuration or native dispatch is installed or performed.

Original recordings, manifests, responses, CV outputs, review databases and captures are private and excluded from Git. A clone alone cannot supply the saved cases. Missing or changed sources withhold the affected case and block its frames and decisions.

Decisions are case-scoped and saved locally with source revisions, stale-decision checks and an append-only audit. Railway retains its existing database. Browser checks use isolated stores and preserve operator decisions. Local cookie/CSRF sessions do not authenticate identity. A saved review request is not a native XProtect alarm.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:PLAYWRIGHT_BROWSERS_PATH=(Resolve-Path runs/tooling/playwright).Path
$env:AW_EVALUATIONS='C:/Users/Administrator/adaptive-watch-private/hafnia-16'
.\runs\tooling\bun-windows-x64\bun.exe frontend/scripts/check-workspace.mjs
.\runs\tooling\bun-windows-x64\bun.exe frontend/scripts/check-negative-review.mjs
```

Actual Edge interactions at 1440x900 and 1920x1080 are recorded under ignored `runs/application-checks/` and `runs/negative-review-release-checks/`. Historical footage and the existing 78-second evidence video remain untouched under `runs/negative-review-checks/`.

See [application behavior and manual orchestration](docs/adaptive-watch/application-completion.md), [original case preparation](docs/adaptive-watch/negative-result-review.md), and [supervised analysis setup](docs/adaptive-watch/setup.md). The former root README is preserved verbatim in [single-case-readme.md](docs/adaptive-watch/single-case-readme.md); older workflows remain in [prior-workflow.md](docs/adaptive-watch/prior-workflow.md).
