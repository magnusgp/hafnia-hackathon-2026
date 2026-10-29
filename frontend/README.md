# Ortru frontend

React 19, TypeScript and Vite. `src/main.tsx` is the only entry. It talks to `ortru.server` through the versioned envelope
API (`src/api.ts`, `src/types.ts`) and never reads files, so private footage is not in the production bundle
(`publicDir: false`).

| File | What it is |
|---|---|
| `src/Exceptions.tsx` | Default screen: the exception queue (live exceptions, then verified earlier records) and the selected investigation |
| `src/Investigation.tsx` | Footage with the detector box drawn only at the corresponding sample, the synchronized Hafnia / local vision timeline, the Watch's review question and decision bar, the native send dialog, evidence details |
| `src/Watches.tsx`, `src/WatchEditor.tsx`, `src/RegionDrawer.tsx` | Watch list and page (lifecycle, schedule, budget, assessments with real progress and failure reasons) and the create/edit flow with region drawing on a camera picture |
| `src/Archive.tsx` | The evidence archive: authentic records and historical experiments |
| `src/tokens.css`, `src/style.css`, `src/ui.tsx` | The Ortru design system: Polar palette extended with Hafnia blue and local-vision violet, type scale, spacing, components |

The mark, favicon and wordmark are editable SVG in `../brand-kit/ortru/`. The design record is `../docs/design/ortru/`.

```powershell
..\runs\tooling\bun-windows-x64\bun.exe run build      # tsc -b, then vite build
```

## Browser acceptance

`scripts/check-ortru.mjs` drives real Edge through the operator's workflow at 1440x900 and 1920x1080: create a Watch (camera,
custom prompt, detector, region, cadence), activate, assess, open the exception, review the evidence, save a decision,
preview and confirm the native handoff, create a second Watch with a different question and camera, and exercise malformed
prompts, unsupported detectors, stale revisions, duplicate sends and persistence. It runs against `tests/ortru_fixture.py`
(fake XProtect, GPU and Hafnia effects and a test transport that cannot reach the Event Server). From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-ortru-check.ps1
```

`scripts/shoot-real.mjs` takes read-only screenshots of the real server; `scripts/shot-html.mjs` screenshots any local HTML file
(used for the design comparison and the deck). `record-deck.mjs` and `deck-preview.mjs` belong to the earlier film.
