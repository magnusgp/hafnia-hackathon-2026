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

Browser checks use real Edge against an isolated demo instance (never the operator's saved decisions):

```powershell
cd ..
.\.venv\Scripts\python.exe scripts\adaptive_watch\make_demo_root.py
.\.venv\Scripts\python.exe scripts\adaptive_watch\record_agent_review.py --root runs\release\demo-app --railway runs\release\demo-railway --evaluations $env:USERPROFILE\adaptive-watch-private\hafnia-16
# start the server on port 8781 with --root runs\release\demo-app --railway runs\release\demo-railway, then:
$env:PLAYWRIGHT_BROWSERS_PATH = (Resolve-Path runs\tooling\playwright).Path
cd frontend; ..\runs\tooling\bun-windows-x64\bun.exe scripts\check-app.mjs ..\runs\release\checks
```

`scripts/shoot.mjs` captures screenshots, `capture-walkthrough.mjs` records the application for the presentation,
`record-deck.mjs` and `deck-preview.mjs` record and preview the deck (see `../presentation`).
