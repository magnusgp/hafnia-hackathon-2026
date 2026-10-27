# Adaptive Watch frontend

The default entry is the single railway negative-result review in `src/negative-review.tsx`. Polar styling is retained. React loads private evidence only from the Python API; `publicDir: false` prevents private assets from entering the build.

## Build and serve on p022

From the repository root, use the existing tools:

```powershell
cd frontend
..\runs\tooling\bun-windows-x64\bun.exe install --frozen-lockfile
..\runs\tooling\bun-windows-x64\bun.exe run build
cd ..
.\.venv\Scripts\python.exe -m adaptive_watch.negative_review_api --root runs/negative-result-review --frontend frontend/dist --port 8776
```

Open http://127.0.0.1:8776 in a browser inside p022 using existing authorized desktop access. Keep the launch terminal open. The server binds to loopback; a localhost URL on a judge's own computer cannot reach p022.

Choose **Review footage**, inspect the footage and acknowledge review, then **Dismiss** or **Save review request**. Decisions persist locally across reloads. The saved state explicitly says **no native event has been sent**. This API cannot configure XProtect or send native events. Local cookie/CSRF sessions are not production operator authentication.

See the [root setup and private-evidence preparation](../README.md) and [acceptance notes](../docs/adaptive-watch/negative-result-review.md). Original recordings, source frames, responses, database files, credentials and generated captures stay outside Git.

## Browser verification

From the repository root:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH=(Resolve-Path runs/tooling/playwright).Path
.\runs\tooling\bun-windows-x64\bun.exe frontend/scripts/check-negative-review.mjs
```

The checks use isolated real-case copies at 1440×900 and 1920×1080. Reports and captures go to ignored `runs/negative-review-release-checks/`, preserving the existing 78-second evidence video, diagnostic comparison image and their sources in `runs/negative-review-checks/`. Those historical assets are not the final narrated submission.

The earlier incident/replay implementation remains in `src/main.tsx`; its historical setup is preserved in [prior-workflow.md](../docs/adaptive-watch/prior-workflow.md).
