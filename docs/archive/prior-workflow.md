# Adaptive Watch

Adaptive Watch helps XProtect security operators investigate persistent objects on pedestrian routes. Repeated observations join an incident so the operator can review source frames, localized stationarity and Hafnia interpretation, save a finding, or dismiss it. Native escalation requires separately validated evidence and explicit human authorization.

## Architecture

- **Windows / p022:** XProtect recorded snapshots and acquisition manifests; the existing Hafnia gateway supplies recorded-interval semantic assessments. Gateway credentials remain in the terminal/private configuration.
- **Linux / p022-linux:** the existing SSH identity runs pinned OWL-ViT on the NVIDIA A10G. Camera-specific geometry and temporal measurements qualify a candidate; they do not measure pedestrian clearance.
- **Evidence and lifecycle:** Python validates source hashes, frame timestamps, camera/interval identity and original Hafnia responses. SQLite retains observations, decisions, escalation intent and dispatch reservations. Decisions reject stale evidence with HTTP 409.
- **Operator UI:** React/TypeScript and Polar styling, served locally by the Python evidence API. Incidents is the default; Demo mode isolates replay controls. Dismissed incidents remain in history. Evidence changes refresh an open investigation and require another decision after a conflict.
- **Native action:** backend-owned, expiring confirmation binds exact immutable payload, evidence revision, destination, configuration and human session. Persistent reservations prevent duplicate/uncertain sends. Transport acceptance is separate from verified Smart Client alarm creation.

## Developer setup

Python 3.11, uv, Bun and installed Microsoft Edge are required for the full local workflow. The backend uses Python's standard library. From a clean checkout:

```powershell
uv sync --frozen
uv run --frozen python -m unittest discover -s tests
cd frontend
bun install --frozen-lockfile
bun run build
cd ..
```

For an empty local workspace (no private evidence required):

```powershell
uv run --frozen python -m adaptive_watch.evidence_api --root runs/local serve --frontend frontend/dist --port 8770
```

Open http://127.0.0.1:8770. No footage or inference results are invented when private inputs are absent.

For the prepared, validated replay on **p022**, open a browser **inside p022** at http://127.0.0.1:8770. Choose **Demo mode**, **New demo session**, then start or step replay. It uses saved XProtect/CV/Hafnia evidence; repeated arrivals are synthetic and add no independent evidence. Six arrivals form two incidents. Replay never makes inference requests or sends native events. The localhost application is not exposed publicly; judges need the existing authorized p022 desktop access.

To start that prepared replay from this repository on p022:

```powershell
uv run --frozen python -m adaptive_watch.evidence_api --root runs/recovery-demo serve --demo-source runs/product-evidence --evaluations C:/Users/Administrator/adaptive-watch-private/hafnia-16 --frontend frontend/dist --port 8770
```

Those private inputs are deliberately excluded from Git. To rebuild the seed from authorized originals, follow the import commands in [frontend setup](../../frontend/README.md). Replay validates originals and fails closed if they are missing or changed.

```powershell
# With the replay server running:
bun frontend/scripts/check-recovery.mjs
# Clean recording, without injected failures:
bun frontend/scripts/capture-operator.mjs
```

`REVIEW_URL` selects the server; `PLAYWRIGHT_BROWSERS_PATH` can select an existing browser tooling directory. Results and footage remain under ignored `runs/`.

## Verified results and remaining limits

See [recovery evidence and release review](recovery-sprint.md) for actual before/after HTTP results, browser recordings, checks and the native blocker. The existing dedicated Adaptive Watch analytics event and scooter-only alarm definition are configured; do not recreate them. No Adaptive Watch event has been sent in this sprint. Geometry approval, coherent recording validation, strict same-interval Hafnia qualification, explicit dispatch approval and Smart Client verification remain gates.

Stationarity uses sampled image-space measurements, with unknown behavior between samples. Largest-box association can switch targets; polygon overlap is not accessible width. No independently measured accuracy improvement or continuous camera-health monitoring is claimed. Local cookie/CSRF protection is not authenticated operator identity or production access control.

## Third-party and pre-existing work

This repository predates Adaptive Watch: the Scene Contracts application, gateway client, recorded assessment tooling and native analytics transport remain as prior work. Historical experiments include a failed fog improvement gate; their results are not Adaptive Watch accuracy claims. See [historical Scene Contracts documentation](operator-mvp.md) and [ML report](../research/checkpoint-a.md).

The UI uses React, TypeScript, Vite, Tailwind, Playwright and locally bundled Google Fonts (Space Grotesk, DM Sans, IBM Plex Mono); exact versions are in `frontend/bun.lock`. Optional ML dependencies and pinned versions are in `pyproject.toml` / `uv.lock`: PyTorch, Transformers/OWL-ViT, NumPy, Pillow, SciPy, scikit-learn and PyAV. XProtect, MilestonePSTools and the Hafnia gateway/model are existing external infrastructure, not authored here. Linux uses its existing compatible CUDA environment. Original evidence, models and platform components remain subject to their own licenses and access permissions.

The submission video must be **under 3 minutes**. Keep the existing Polar slide deck as the narrative and use short, explicitly labeled replay clips as evidence. Release changes require review; this branch must not be merged automatically.
