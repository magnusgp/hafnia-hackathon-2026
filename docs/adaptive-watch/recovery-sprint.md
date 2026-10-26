# Recovery sprint evidence — 26 October 2026

## Product changes

Incidents is the default view. Replay setup, stepping and reset are under Demo mode. The Polar styles and slide deck are unchanged. The app no longer contains the presentation tagline or speculative capability roadmap.

The investigation adopts refreshed evidence without discarding the review note. Local replay changes refresh the open record; two-second polling also detects arrivals from another browser. On a decision conflict, the UI loads current evidence/state, explains HTTP 409 and requires another operator action. It never resubmits the stale decision automatically. Successful decisions update the visible incident immediately. Dismissed incidents leave the open queue and remain in history.

Save review and Dismiss incident form one decision area. Escalate to XProtect is shown only when the backend validates the prerequisites. Preparing escalation records intent without sending; an explicit expiring confirmation is still required. Browser evidence IDs are checked during preparation, and the saved review must match the current observations/assessments. Immutable payload, evidence revision, destination and configuration remain bound on the backend. Accepted transport is labeled separately from unverified alarm creation.

Replay-session selection and mutation checks share one lock, so reset cannot swap the active store between validation and mutation. Backend 409 diagnostics include their causes in development logs; the browser receives a sanitized status without source paths, XML, hashes or credentials.

## Reproduced failure and fixed checks

The original `3b14be9` frontend was built into an isolated ignored baseline directory and served on localhost:8771. In Edge: step once, open the incident, step again while it remains open, then Mark reviewed. The browser submitted one observation ID while the server held two. Actual response: **HTTP 409**, `Evidence changed; reload before deciding`; zero decisions saved. Screenshot and machine-readable request/server IDs are retained privately in `runs/recovery-capture/original-failure.png` and `original-failure.json`.

The fixed browser regression runs at **1440×900 and 1920×1080**. It verifies:

- Start/continue, pause, step, reset and disabled replay controls, including a real rejected stale cursor followed by successful retry.
- Open investigation during replay; another arrival joins it and preserves the typed note.
- A deterministic arrival racing Save review produces HTTP 409 and zero saved decisions; explicit retry produces HTTP 200.
- Save review and Dismiss incident return HTTP 200, change visible state, survive reload and appear correctly in open queue/history.
- Playback/pause, sample slider, all timeline buttons, CV overlay, draft region and recorded Hafnia assessment selection.
- Unavailable replay native preparation/confirmation return HTTP 409; missing CSRF authorization returns HTTP 403. No native action is sent.
- Six arrivals remain two incidents of three observations each, with no independent evidence claimed. No page errors, external browser requests or horizontal overflow.

Python regression checks include stale review/dismiss/escalation evidence, dismissal during replay, source integrity, immutable confirmation/session/destination/expiry, native stale-browser preparation, uncertain-send reservation and duplicate suppression. Tests mock native transport; their accepted/uncertain messages do not describe actual sends.

The separate clean capture script injects no failures and asserts zero failed HTTP responses and zero page errors. Both requested sizes produce short private WebM recordings showing grouping, saved CV/Hafnia investigation, successful review/dismissal and persistence/history. The submission itself must remain under three minutes and retain the slide deck as its main narrative.

## Native blocker

The existing dedicated event and scooter-only alarm definition were retained. Read-only SSH using the existing identity succeeded; `nvidia-smi` returned **NVIDIA A10G**. Retained final scooter CV identifies Linux CUDA on p022-linux and a qualifying sampled run. However, its spatial file is **unapproved**, and its root lacks matching qualified Hafnia evidence and a joined dispatch proposal. Coherent recording review, same-interval qualification, explicit authorization for the first actual dispatch and separate Smart Client verification remain outstanding. No new inference or native send was performed during recovery. See [exact integration checkpoint](final-integration.md).

## Release review

Base: GitHub main `8833c744910bd73dff06d498d361b435558339a5`; starting feature revision `3b14be9f92a47f8b06be4e1d820e1575b85f7ddd`. The entire feature diff includes prior Adaptive Watch CV/evaluation experiments, evidence acquisition/joining, lifecycle/dispatch guards, UI, tests and public result reports. It retains Scene Contracts as pre-existing work. Review the complete file manifest in [release-files.txt](release-files.txt), not just this sprint's UI correction.

Review commands:

```powershell
git diff 8833c744910bd73dff06d498d361b435558339a5...feat/adaptive-watch --stat
git diff 8833c744910bd73dff06d498d361b435558339a5...feat/adaptive-watch
```

The exact patch is exported privately to `runs/adaptive-watch-release.patch`. Merge/release approval remains outstanding; no automatic merge. Existing unrelated working changes to evaluation/gateway scripts, the operator checkpoint, presentation files, evidence export helper and geometry review helper are preserved and excluded from the recovery commit. Private footage, identities, credentials, SQLite files and operator configuration are excluded from Git.
