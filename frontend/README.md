# Adaptive Watch frontend

The current default entry is the single railway negative-result review in `src/negative-review.tsx`. Build as below, then serve with `python -m adaptive_watch.negative_review_api --root runs/negative-result-review --frontend frontend/dist --port 8776`. See the [current setup](../README.md) and [acceptance notes](../docs/adaptive-watch/negative-result-review.md).

The instructions below describe the preserved earlier incident workflow in `src/main.tsx`; that entry is not the current default build.

Polar styling is retained. React loads private evidence only from the Python API; `publicDir: false` prevents private assets from entering the build.

## Build and serve

```powershell
cd frontend
bun install --frozen-lockfile
bun run build
cd ..
uv run --frozen python -m adaptive_watch.evidence_api --root runs/product-evidence serve --frontend frontend/dist
```

Open http://127.0.0.1:8765. The default view is Incidents. Decisions persist on the server; dismissals leave the open queue and remain in history. Native availability comes from the backend, with a separate explicit confirmation before sending.

For development, run `bun run dev` in `frontend`; its localhost:4174 proxy requires the evidence server on localhost:8765.

## Import authorized saved originals

```powershell
$evaluations = 'C:/Users/Administrator/adaptive-watch-private/hafnia-16'
uv run --frozen python -m adaptive_watch.evidence_api --root runs/product-evidence import --joined runs/hybrid/sidewalk-v2/scooter-joined.json --cv runs/hybrid/sidewalk-v2/escooter_left_across_sidewalk.json --manifest runs/xprotect/escooter_left_across_sidewalk_20261022T110435Z/manifest.json --evaluations $evaluations
uv run --frozen python -m adaptive_watch.evidence_api --root runs/product-evidence import --joined runs/hybrid/sidewalk-v2/bin-joined.json --cv runs/hybrid/sidewalk-v2/bin_pushed_over_onto_sidewalk.json --manifest runs/xprotect/bin_pushed_over_onto_sidewalk_20261022T110430Z/manifest.json --evaluations $evaluations
```

Fresh schema-v2 imports additionally require their own spatial and geometry inputs. Never promote retrospective evidence to fresh dispatch eligibility.

The [root README](../README.md) gives isolated replay and browser validation commands. `scripts/check-recovery.mjs` tests in-progress replay, real stale-evidence HTTP 409 recovery, persistent review/dismissal, history, playback, disabled controls and unavailable native calls at both target resolutions. `scripts/reproduce-stale.mjs` targets the original frontend built into an isolated baseline server on port 8771; it proves the old failure rather than expecting the fixed UI to fail.

All recordings, source frames, responses, database files, credentials and identities stay outside Git. Local cookie/CSRF sessions are not production operator authentication.
