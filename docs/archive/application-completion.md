# Workspace behavior and remaining analysis work

The default entry is operational for source-verified saved-evidence investigation and local review decisions. Fresh browser analysis is **not implemented end to end**. New assessment reports exact runtime handoff blockers and saves a readiness failure, never a mock assessment or purported inference job.

## Evidence

| Case | Original interval on 22 October 2026, UTC | Interpretation |
| --- | --- | --- |
| Railway | 11:03:39-11:03:52 | Original negative Hafnia result, Linux person/region proximity, original MKV and 26 half-second snapshots. Review recommended; proximity does not establish railway entry. |
| School gate | 11:04:39-11:04:52 | Two original negative prompts and 13 timestamped snapshots. Semantic uncertainty: narrative describes manipulation while conclusion requires opening. No independent CV or original video. |
| Scooter | 11:04:48-11:05:01 | Hafnia support and original Linux OWL-ViT localization, 13 snapshots. Six stationary samples span 5 seconds; maximum center drift 0.00690 image units; minimum draft box/walkway overlap 43.0%. |
| Bin | 11:04:31-11:04:43 | Hafnia support and original Linux OWL-ViT localization, 12 snapshots. Four stationary samples span 3 seconds; maximum center drift 0.00379 image units; minimum draft box/walkway overlap 77.9%. |

Gate prompt diagnostics refer to the **separate 27 October 11:55:49-11:56:02 UTC recording**. Exact requests and responses are verified against the existing diagnostic ledger and report; the recording manifest and original video are checked. They appear only in a separately dated section and are never aligned to the 22 October frames. Prompt families and repeats are not independent events.

Sidewalk validation reuses `EvidenceStore.register`: exact name/GUID, original manifest, submitted/returned Hafnia request, original responses, CV localization, frames and temporal policy. Measurements are recomputed and compared with the saved join. Railway retains the unchanged `ReviewStore` verifier/action API. Gate verifies saved original response files against adjudication hashes, exact camera/interval/request identity and snapshot hashes. The historical gate manifest lacks frame hashes; existing adjudication supplies them, while all original manifest fields are checked without rewriting it.

Only verified, available cases appear as cards. Source failures appear as **Insufficient evidence** in a separate notice; direct case/frame reads and decisions fail. Unknown cases return 404, unavailable sources 422, stale or cross-case revisions 409. No case falls back to another case's footage. Operator verification is recommended for all four cases. Draft overlap does not establish obstruction, accessible clearance, intent or persistence beyond the final measured sample.

## Local decisions

Railway retains `runs/negative-result-review/review.sqlite3`. The other cases use case-keyed rows in `runs/application/workspace.sqlite3`, with case/source/state revisions, transactional decisions and an append-only audit. Decisions require beginning review and acknowledging relevant footage. Non-default annotations need supporting notes. Review status and human annotations do not rewrite model responses. A locally saved request never sends a native event or creates an XProtect alarm. Local sessions protect against CSRF but do not authenticate identity.

## New assessment and manual orchestration

The picker intersects the existing authorized camera catalog with `config/camera-capabilities.json`, which supports persistent-object analysis for scooter and bin only. Saved availability does not imply live recording coverage. The backend validates whole-second UTC bounds and a past 12-17 second interval within 24 hours; historical source cases cannot be resubmitted.

Start assessment records a readiness failure in `assessment-readiness.sqlite3`, separately from review and inference ledgers, with `inferenceSubmitted=false` and `recordingAcquired=false`. It performs no authentication, acquisition, summary submission, inference retry or native dispatch.

The exact integration gap is in `scripts/adaptive_watch/incident.py`: `analyze` invokes SSH/SCP with operator-selected transport configuration, pauses for continuity review, and calls `terminal_login`, which requires `sys.stdin.isatty()`. The HTTP service has no supported handoff for a prepared authenticated `Gateway`, CUDA transport, or source-bound continuity review. Launching that interactive script from an HTTP worker would not prepare the authenticated runtime.

These stages still require the existing supervised workflow:

1. Acquire the exact interval through `scripts/acquire_recording.ps1`; verify recording-sequence coverage, source identities and continuity without synthetic loop boundaries.
2. Review camera-specific spatial geometry and register/approve the current camera view where required. Saved draft polygons do not grant fresh approval.
3. Configure the existing SSH identity and Linux interpreter, transfer verified sources and run the existing pinned `sidewalk_cv.py` on Linux CUDA.
4. Prepare the interactive authenticated Hafnia runtime, then use `Evaluation` with its existing claim-before-POST ledger. Reconcile unknown submission outcomes instead of resubmitting; poll existing known summary IDs.
5. Assemble the same-camera, same-interval result through the existing integrity checks. Automatic import of a fresh supervised run into this workspace is not offered.

A maintainer must connect those stages to a prepared runtime adapter and operator continuity/geometry review before browser submission can be enabled. The inference engines need no rebuilding. Native XProtect configuration and dispatch are outside this work.

## Verification and walkthrough

`frontend/scripts/check-workspace.mjs` records actual Edge interactions at 1440x900 and 1920x1080: four verified cases, railway video/UTC alignment at frames 7, 8, 11, 18, 19, 25; railway follow-up saved; scooter dismissed; independent reload persistence; bin/gate investigation; explicit New assessment blocker; unknown and unavailable sources. Recording captions are injected annotations, not product UI. A separate server deliberately omits the original response directory without changing originals.

The full railway regression additionally checks region drawing, overlays, save/dismiss/reopen, stale revisions, native-action rejection and capture durations. All browser decisions use isolated stores. Historical footage, original operator decisions and evidence videos remain untouched. Raw captures stay in ignored `runs/`.

See `runs/application/verification.json` for final exact counts and artifact paths. The production build contains application assets and fonts only; private footage is served by Python.

## Branch constraint

The checkout began at `e8378c207467f5f7804ca835439532688e3c7711` with pre-existing uncommitted changes, all retained. Creating `feat/application-completion` failed because this session grants only read access to `.git`; approval escalation is unavailable. A managed detached worktree was created at the same base while checking the available path, but no implementation or evidence was moved there. Implementation remains in the shared checkout, unmerged. `runs/application/application-completion.patch` contains only this task's changes for applying to the requested branch when Git writes are available.
