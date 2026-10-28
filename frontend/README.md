# Adaptive Watch frontend

React 19, TypeScript and Vite. `src/app.tsx` is the only entry. It reads the unified case view model from
`adaptive_watch.app_api` (`/api/casebook`, `/api/cases/<id>`), never from files, so private footage is not in the
production bundle (`publicDir: false`).

- `src/app/Stage.tsx` footage with the detector box and region, drawn only on the frame the detector measured
- `src/app/Timeline.tsx` three evidence lanes on one clock (Hafnia, local vision, footage review)
- `src/app/Brief.tsx` the two signals and the review exception XProtect receives
- `src/app/Dialogs.tsx` decision, XProtect send confirmation, evidence details, New assessment

```powershell
..\runs\tooling\bun-windows-x64\bun.exe run build
```

Browser checks use real Edge against an isolated session (never the operator's saved decisions). Start one with
`scripts\review.ps1 -NoBrowser` from the repository root (port 8781), then, in this order (the second expects the
review the first saves):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = (Resolve-Path ..\runs\tooling\playwright).Path
..\runs\tooling\bun-windows-x64\bun.exe scripts\check-app.mjs ..\runs\review-notes\checks http://127.0.0.1:8781
..\runs\tooling\bun-windows-x64\bun.exe scripts\check-release.mjs ..\runs\review-notes\checks http://127.0.0.1:8781
```

Stop it with `scripts\review.ps1 -Stop`; `-Reset` gives a fresh session.


`frontend/scripts/shoot.mjs` captures screenshots, `capture-walkthrough.mjs` records the application for the presentation,
`record-deck.mjs` and `deck-preview.mjs` record and preview the deck (see `../presentation`).
