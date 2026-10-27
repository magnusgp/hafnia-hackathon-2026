# Adaptive Watch — negative-result review

One saved railway case, one Polar operator screen. A negative Hafnia assessment plus an independent CV proximity observation requests human review. Proximity does not establish entry; disagreement does not establish which model is correct.

The original Hafnia evidence, Linux CV implementation, XProtect integration and Polar identity are preserved. Historical incident/replay code remains in the repository; this workflow adds no dashboard or replay mode. The former root README is preserved in [prior-workflow.md](docs/adaptive-watch/prior-workflow.md).

## Open the prepared case

```powershell
.\.venv\Scripts\python.exe -m adaptive_watch.negative_review_api --root runs/negative-result-review --frontend frontend/dist --port 8776
```

Open http://127.0.0.1:8776. Choose **Review footage**, inspect the relevant moments, and confirm you reviewed the footage. Then **Dismiss** or **Request XProtect review**. Requests are saved locally; the server cannot configure XProtect or dispatch events. Evidence details contain the original response, summary ID, frame links, region editor, diagnostic context and original hashes.

## Reproduce from authorized originals

Private footage and responses are deliberately excluded from Git. Preparation fails if any required original is missing or changed. No inference, Linux ML job or network call is made.

```powershell
.\.venv\Scripts\python.exe scripts/adaptive_watch/prepare_negative_review.py --root runs/negative-result-review --response C:/Users/Administrator/adaptive-watch-private/hafnia-16/46b7cab7070701d4518d3897e7f958f708e4ef0d2ded68d4ec4e7f97930ec752.json --decode-deps runs/reliability-fresh/decode-deps
.\.venv\Scripts\python.exe scripts/adaptive_watch/prepare_review_event.py --root runs/negative-result-review
cd frontend
..\runs\tooling\bun-windows-x64\bun.exe run build
cd ..
```

Use the existing pinned PyAV/Pillow environment, or pass its package directory with `--decode-deps`. A prepared import is reused after integrity verification; it is never silently overwritten.

## Checks and submission assets

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
$env:PLAYWRIGHT_BROWSERS_PATH=(Resolve-Path runs/tooling/playwright).Path
.\runs\tooling\bun-windows-x64\bun.exe frontend/scripts/check-negative-review.mjs
.\runs\tooling\bun-windows-x64\bun.exe frontend/scripts/capture-negative-comparison.mjs
.\.venv\Scripts\python.exe scripts/adaptive_watch/package_negative_review_video.py --decode-deps runs/reliability-fresh/decode-deps
```

Browser checks use isolated copies of the real case at 1440×900 and 1920×1080. Captures, the diagnostic comparison PNG, operator WebMs, the final MP4 and validation reports are kept under ignored `runs/negative-review-checks/`. The final MP4 includes the original XProtect export, saved CV overlay and operator flow, with a hard limit below three minutes. No complete presentation is generated.

See [implementation and acceptance notes](docs/adaptive-watch/negative-result-review.md) for exact provenance, behavior and remaining authorization gates.
