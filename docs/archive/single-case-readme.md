# Adaptive Watch — negative-result review

One saved railway case, one Polar operator screen. A negative Hafnia assessment plus an independent CV proximity observation requests human review. Proximity does not establish entry; disagreement does not establish which model is correct.

The original Hafnia evidence, Linux CV implementation, XProtect integration and Polar identity are preserved. Historical incident/replay code remains in the repository; this workflow adds no dashboard or replay mode. The former root README is preserved in [prior-workflow.md](prior-workflow.md).

## Open the prepared case

```powershell
.\.venv\Scripts\python.exe -m adaptive_watch.negative_review_api --root runs/negative-result-review --frontend frontend/dist --port 8776
```

Run the command from the repository root on Windows machine **p022**, using its existing prepared evidence and production build. Open http://127.0.0.1:8776 in a browser **inside p022**. Judges need existing authorized desktop access to p022; a localhost URL on their own computer will not reach it. The server accepts loopback access only.

Choose **Review footage**, inspect the relevant moments, and confirm you reviewed the footage. Then **Dismiss** or **Save review request**. The resulting state says the decision is saved locally and **no native event has been sent**. The server cannot configure XProtect or dispatch events. Evidence details contain the original response, summary ID, frame links, region editor, diagnostic context and original hashes.

The launch command runs in the foreground. Keep that PowerShell terminal open for the judging session; closing it stops that launch. If the application is unavailable, open PowerShell on p022, run `cd C:\Users\Administrator\dev\hafnia-hackathon-2026`, and run the launch command above. No Windows service is installed.

## Reproduce from authorized originals

**Original footage is private**, as are the saved responses and generated captures; they are deliberately excluded from Git. A Git clone alone does not include the prepared evidence. Preparation fails if any required original is missing or changed. No inference, Linux ML job or network call is made.

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
```

Browser checks use isolated copies of the real case at 1440×900 and 1920×1080. Release captures and browser reports are kept under ignored `runs/negative-review-release-checks/` so the existing submission assets stay intact.

The preserved **78-second evidence video** (`adaptive-watch-negative-review.mp4`), diagnostic comparison PNG and their original sources remain under ignored `runs/negative-review-checks/`. The video includes the original XProtect export, saved CV overlay and automated operator flow. These are historical evidence assets and can show the earlier action wording; they are **not the final narrated submission video**. Do not overwrite them when preparing the submission. The outstanding submission work is to combine the existing Polar slides, narration, limitations and current UI evidence into a final video under three minutes, verify its claims and playback, and submit it with the repository link and judge-access instructions. Human entry verification remains outstanding; the automated walkthrough is not human attestation. Native XProtect configuration and dispatch require separate authorization and are outside this release.

See [implementation and acceptance notes](../research/negative-result-review.md) for exact provenance, behavior and remaining authorization gates.
