# Adaptive Watch frontend

`src/application.tsx` is the default multi-case entry. It loads source-verified records from `adaptive_watch.workspace_api`. `publicDir: false` excludes private evidence from the production bundle.

`src/railway-review.tsx` preserves the video-focused railway investigation extracted from `negative-review.tsx`. Shared evidence details, source identity, review state, snapshot viewing and review controls live in `src/evidence-components.tsx`. The single-case mounting implementation remains in `src/negative-review.tsx`; the current app also opens railway at `/#case/railway`. Historical `src/main.tsx` and unrelated presentation files are preserved and are not default entries.

Run `../runs/tooling/bun-windows-x64/bun.exe run build` from this directory. Vite uses its runner config loader to avoid esbuild traversing restricted parent directories when bundling config. Start the workspace API using the [root README](../README.md).

From the repository root, run the Python suite, `frontend/scripts/check-workspace.mjs`, and `frontend/scripts/check-negative-review.mjs` using the installed Bun executable. Set `PLAYWRIGHT_BROWSERS_PATH` to `runs/tooling/playwright` and `AW_EVALUATIONS` to the private Hafnia response directory. Both scripts record actual Edge interactions at 1440x900 and 1920x1080 using isolated decision stores. No inference or native events are sent.

New assessment currently returns a persisted readiness failure. Authenticated Hafnia runtime handoff, Linux CUDA transport, fresh acquisition and continuity review require the supervised workflow. See [application notes](../docs/adaptive-watch/application-completion.md).
