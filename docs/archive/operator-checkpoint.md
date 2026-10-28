# Operator checkpoint — 22 October 2026

Run in a user-opened PowerShell on p022, from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\adaptive_watch\evaluate.py runs\hybrid\plan.json --root C:\Users\Administrator\adaptive-watch-private\hafnia-16 --apply
```

The password prompt is terminal-only, ignores the password environment variable, and uses the existing Gateway client. Do not paste the password into chat. This command authorizes only the saved sixteen inline inference requests. It resumes known IDs and blocks ambiguous submissions. Rerun the same command to poll pending IDs; never delete the ledger or use a fresh root to retry. Aggregate outcomes are in the external root's aggregate.json; raw responses stay there. If the saved intervals expire, stop and review recording availability; do not silently replace them with current camera loops.

Geometry review: private runs/hybrid/railway-geometry-review.svg and railway-geometry-review.json annotate five samples from the saved overlay, with revised track-bed polygon in cyan. This is same-clip calibration, not independent validation. Clear standing track-bed entry is bracketed 11:03:48.013–48.513 UTC. Original membership onset at 44.513 is 3.5–4 seconds earlier; seated contact is uncertain. Missed/false occupancy rates remain unmeasured. Corrected entry logic allows only a review candidate from the polygon; visual contact and descent must be established before interpreting it as entry. No native dispatch is permitted.

No Hafnia results are currently available, so no completed hybrid evidence record or scenario comparison can be claimed. Join only the railway request for 11:03:39–11:03:52 with the matching CV manifest; retain exact interval and all model metadata. Proposed operational decision remains operator_review_required, never automatic dispatch.

Git: HEAD and cached origin tracking ref both identify 23398a7 before these changes, but historical handoff says publishing failed. Live ls-remote failed due to network connectivity; cached equality is not remote verification. Private milestone.bundle contains 23398a7. Saved Linux CV artifact identifies 1163ddf; live Linux revision is unverified. New changes remain in the working tree for review.

Git Credential Manager is configured as credential.helper=manager. In an interactive PowerShell, after reviewing and committing changes, run git push origin feat/adaptive-watch and complete GCM's browser authentication. No force push. Then use git ls-remote origin refs/heads/feat/adaptive-watch and git rev-parse HEAD to compare. On Linux, inspect git status and git rev-parse HEAD before fetching; preserve dirty work, fetch origin, and fast-forward only the intended branch. No credentials belong in chat or bundles. GitHub CLI was not found on PATH.

First railway alarm demonstration: first compare Hafnia against these same recording samples, resolve geometry uncertainty with operator review, then seek separate authorization for a distinct railway review event definition and one deterministic XML payload. Keep the failed fog improvement gate visible. No alarm or new definition is authorized now.
