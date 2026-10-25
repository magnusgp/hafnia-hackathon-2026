# Adaptive Watch — Polar product foundation

React + TypeScript + Vite + Tailwind CSS 4, with the approved Polar tokens and
locally bundled Space Grotesk, DM Sans and IBM Plex Mono. No scenario evidence is
embedded in React. Python owns the private evidence index and source validation.

## Import the existing real records

Run from the repository root. Substitute the existing private Hafnia directory if
its location differs; do not copy it into Git.

```powershell
$evaluations = 'C:/Users/Administrator/adaptive-watch-private/hafnia-16'
.venv/Scripts/python.exe -m adaptive_watch.evidence_api --root runs/product-evidence import --joined runs/hybrid/sidewalk-v2/scooter-joined.json --cv runs/hybrid/sidewalk-v2/escooter_left_across_sidewalk.json --manifest runs/xprotect/escooter_left_across_sidewalk_20261022T110435Z/manifest.json --evaluations $evaluations
.venv/Scripts/python.exe -m adaptive_watch.evidence_api --root runs/product-evidence import --joined runs/hybrid/sidewalk-v2/bin-joined.json --cv runs/hybrid/sidewalk-v2/bin_pushed_over_onto_sidewalk.json --manifest runs/xprotect/bin_pushed_over_onto_sidewalk_20261022T110430Z/manifest.json --evaluations $evaluations
.venv/Scripts/python.exe -m adaptive_watch.evidence_api --root runs/product-evidence serve
```

The same importer supports fresh schema-v2 `joined.json` artifacts when supplied
with their original CV, manifest, Hafnia directory and `--spatial` configuration.
It rebuilds fresh joins before accepting them. Import is idempotent for identical
joined bytes. New artifact versions get distinct IDs; no evidence is overwritten.

## Start the frontend

In a second terminal:

```powershell
cd frontend
../runs/tooling/bun-windows-x64/bun.exe install
../runs/tooling/bun-windows-x64/bun.exe --bun run dev
```

Open http://127.0.0.1:4174/#/monitoring. Selecting either incident navigates to
`#/investigation/<actual-incident-id>`. Vite proxies `/api` to localhost:8765.
API endpoints: `GET /api/incidents`, `GET /api/incidents/ID`, and
`GET /api/incidents/ID/frames/INDEX`. There are no mutation/dispatch endpoints,
no gateway credentials and no cross-origin API access. Indexed frames are
hash-checked again before serving.

For a single local server, build with `bun --bun run build`, then from repository
root run:

```powershell
.venv/Scripts/python.exe -m adaptive_watch.evidence_api --root runs/product-evidence serve --frontend frontend/dist
```

Open http://127.0.0.1:8765/#/monitoring. Stop an already running evidence server
before changing its serving mode. Use the development proxy or this Python server;
`vite preview` alone does not proxy the evidence API.

Private evidence is never copied into public build output (`publicDir: false`).
The earlier `prepare_evidence.py` export is not used by this application. Keep old
private exports, recordings, SQLite indexes, screenshots and runs out of Git.
Camera rules are in `../config/camera-capabilities.json`; their regions are draft.
The fresh incident command requires `--camera` and a separate camera-specific
spatial approval file. Python approval, exact XML digest and persistent dispatch
ledger gates remain authoritative. Frontend notes and hold are session-only.

## Validation and live gates

```powershell
# Repository root
.venv/Scripts/python.exe -m unittest discover -s tests -v
# Frontend directory; evidence API + Vite must already be running
../runs/tooling/bun-windows-x64/bun.exe --bun run build
../runs/tooling/bun-windows-x64/bun.exe --bun run check:evidence
```

Browser checks use installed Edge; alternatively install Playwright's msedge
channel in an environment that supports it. `REVIEW_URL` can select the Python
server instead. Checks load both actual incident IDs, verify camera/image identity,
filters, overlays, seeking, local hold, provenance and unknown IDs at 1440×900 and
1920×1080. Private results are under ignored `runs/product-integration/`.

See [product integration checkpoint](../docs/adaptive-watch/product-integration.md)
for actual validation results, the rejected fresh loop-containing acquisition,
Linux SSH blocker and exact outstanding native alarm approvals/verification.
The presentation remains outside the build and was not extended.
