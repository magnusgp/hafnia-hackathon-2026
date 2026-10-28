# Fresh reliability preflight — 26 October 2026

The October 22 execution plan is superseded and fails the strict recording-age gate. Its prompts, responses, predictions, annotations and empty submission ledger remain unchanged. The new execution plan preserves all four original full prompts and experiment IDs, explicitly binds fresh sources, and passes offline preflight. **No inference has been submitted.**

Submission recommendation: **GO for the four-request diagnostic batch; stop before submission.** Authenticated preflight succeeded at 2026-10-26 22:26:20 UTC and is hash-bound to this fresh plan. The subsequent authenticated quota read reports daily limit 500, used 0, remaining 500, reset 2026-10-27 00:00 UTC. Exact-source recording coverage also passes. The proposed batch is four diagnostic assessments, not validation of a flagship detector. The independent-verifier flagship remains NO-GO because there is no independent entry/negative dataset and seated-contact ambiguity remains unresolved.

## Four fresh requests

| Original experiment ID, unchanged | Date / start UTC | End UTC | Duration |
|---|---|---|---:|
| `REL26-B-railway-v3-r01` | 2026-10-26 22:03:53 | 22:04:06 | 13 s |
| `REL26-B-railway-v4-r01` | 2026-10-26 22:03:53 | 22:04:06 | 13 s |
| `REL26-B-gate-v3-r01` | 2026-10-26 22:03:51 | 22:04:03 | 12 s |
| `REL26-B-gate-v4-r01` | 2026-10-26 22:03:51 | 22:04:03 | 12 s |

Total proposed new requests: **4**. Additional negative-control requests: **0**. Sixteen saved assessments remain reused. These four calls cover two source-loop families already observed in October 22 footage; fresh recordings do not add independent events. Original gate v3/v4 definitions broaden the tool-specific task to visible handling, so decision changes cannot isolate wording from task-definition effects.

Fresh source identity is a hash-bound local acquisition ID, not an invented native XProtect recording GUID:

| Source | Manifest / acquisition SHA-256 | MKV SHA-256 |
|---|---|---|
| Railway | `5bf98d4079516852557947f87d7ec8dc270e352d368e72ace81336036d838a8e` | `c3ed451cb493627515685f699fb59ad60d08a2de64aa08f6bc9fcbae1c24e23b` |
| Gate | `71847f70e954f3bd73f99675c93b0f66366158b2f05dd1d4b601f987a237c1f7` | `2f1db63bf7ed471c530390ab124be271deeb6a4bce386d711914511a9297b3f8` |

Actual camera GUIDs, sequence coverage, original exports, frames and review records remain private under `runs/reliability-fresh/`. The collector exposes sequence coverage rather than a native immutable recording ID; the execution plan records this limitation. Every entry retains full prompt, camera, source ID and manifest hash, UTC bounds, ground-truth assessment, review hash, `model_response: null` and `parse_status: not_submitted`. Future raw responses and parse results belong in the same persistent ledger, alongside its archived full source/ground-truth plan.

## Loop inspection and whole-plan checks

Read-only XProtect acquisition produced two one-minute source exports, followed by separately acquired exact selected intervals: 26 railway snapshots and 24 gate snapshots with per-frame hashes and server UTC timestamps. Both requested intervals are covered by existing recording sequences. Snapshot order, source hashes, camera identity, UTC bounds and source/annotation binding pass. Old October 22 bounds are rejected; the 24-hour rule is also checked immediately before each potential POST. No age exception was added. Earliest expiry is **2026-10-27 22:03:51 UTC**; after that the full batch needs another explicit source refresh and review.

The gate reset was first bracketed at 03.865–04.365; closer inspection found a reset already present in the 03.965 snapshot. Therefore the first candidate, 22:03:52–22:04:04, was rejected and preserved untouched. The final gate request ends at 03.000, before that reset. Railway's next observed reset is bracketed 22:04:06.813–07.313, after its selected end.

Both original selected exports were decoded locally and all 130 frames of each stream inspected for visible discontinuity. Neither selected export contains a visible reset. Railway PTS runs 0.1–13.0 seconds. Gate PTS runs 0.0–12.9 seconds despite a 12-second requested interval; export pre-roll/keyframe behavior and absolute PTS origin are unverified. Do not equate decoded span with exact request duration or invent absolute frame times. UTC identity comes from the actual XProtect interval and timestamped snapshots; no clips were fabricated or trimmed. A hash-bound continuity addendum preserves this distinction.

No source recording was transferred to Linux. Automatic review rejected that transfer, and the work continued with local decoding using the existing pinned PyAV 13.1.0 and Pillow 11.0.0 versions in isolated private tooling. Original files were not edited.

## Why CV flags too early

The saved Linux Faster R-CNN predictions were re-read without new inference, training, threshold changes or modification. Person score remains 0.5. The original and v3 near-platform edge joins normalized `(0.25, 0.32)` to `(0.62, 1.0)`; changing the far-platform boundary leaves this edge unchanged.

At 11:03:44.013 the seated person's box-bottom proxy is `(0.501994, 0.816871)`, 15.28 horizontal pixels on the platform side of that edge. At 44.513 it becomes `(0.503236, 0.785023)`: about **1.03 px right and 15.29 px up**. It now lies only **0.173 horizontal pixels** on the trackward side and membership flips positive. The box bottom is not an anatomical foot or a contact measurement. This crossing is compatible with bounding-box/posture variation while seated; it does not establish descent.

| Reviewed stage in original October 22 source | Frame indices / UTC | V3 geometric flags | Interpretation |
|---|---|---:|---|
| Platform approach | 0–3 / 11:03:39.013–40.513 | 0/4 | Visible platform presence |
| Platform-edge proximity | 4–5 / 41.013–41.513 | 0/2 | Proximity; frame 5 has overlapping track hypotheses 1, 7 and 8 |
| Seated platform edge | 6–17 / 42.013–47.513 | 7/12 | Contact ambiguous; warning only, not entry |
| Visible descent | 18 / 48.013 | 1/1 | Descent visible; exact bed contact partly occluded |
| Confirmed track-area entry | 19 / 48.513 | 1/1 | First sampled clearly established track-bed presence |
| Subsequent track occupancy | 20–23 / 49.013–50.513 | 4/4 | Visually established sampled track presence |
| Far-platform exit | 24–25 / 51.013–51.513 | 0/2 | Transition ambiguous, then far-platform negative |

The candidate starts **3.5–4 seconds early**. It flags 0/6 clear pre-entry negatives, 8/13 ambiguous pre-entry samples and 5/5 clear post-entry samples. Ambiguous seated samples are not counted as proven false physical occupancy. Ten track hypotheses remain hypotheses; no identity fragments were silently joined.

Separate outputs are required: **proximity candidate** from geometry versus **visually confirmed entry** from reference review. The latter is not a newly implemented automatic detector. No timestamp delay, margin, persistence or box-shape threshold was tuned to move this onset. These frames remain calibration; no independent accuracy claim follows. Exact boxes, footpoints, margins, track IDs and all 26 frame interpretations are in [railway-frame-audit.json](../../../results/reliability/railway-frame-audit.json); [railway-timing.svg](railway-timing.svg) provides a sanitized presentation comparison.

## Relevant controls

The eleven-camera catalog contains one railway scene and one gate scene. The fresh railway platform-only period spans about 3.5 seconds; the selected gate approach spans about one second. Seated edge contact is ambiguous. Extending these periods to 12 seconds would include positive action or a loop reset. No eligible distinct task-matched negative is established. Other street/traffic cameras are domain-mismatched; their repeated loops cannot supply independent hard negatives.

The additional control plan is explicitly empty and its rejected candidates retain source IDs and timestamps in [fresh-controls.json](../../../results/reliability/fresh-controls.json). Keep Stage C at zero until distinct, coherent platform-only or gate-without-manipulation footage is available. Authorization and intent are not negative-label criteria.

## Reproduce and authenticate without inference

Private source inputs are required; they are not in Git. The fresh binder verifies the old experiment ledger has no attempts before retaining its IDs. It reads the original prompt matrix and preserves the original frozen plan and accepted annotation files.

```powershell
.venv/Scripts/python.exe scripts/reliability_fresh.py --root runs/reliability-fresh --railway-manifest runs/reliability-fresh/selected/person_on_railway_tracks_20261026T220353Z/manifest.json --gate-manifest runs/reliability-fresh/selected/school_gate_break_in_night_20261026T220351Z/manifest.json
.venv/Scripts/python.exe scripts/reliability_runner.py --root runs/reliability-fresh/operator-batch --plan runs/reliability-fresh/execution-plan.private.json --review runs/reliability-fresh/fresh-signoff.private.json
powershell -ExecutionPolicy Bypass -File scripts/reliability_availability.ps1
```

For the one authenticated preflight, use a user-opened PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reliability_preflight.ps1
```

After the offline status, enter the password locally and press Enter; characters are hidden. This mode logs in once, reads summary history and system quota information, writes a plan-bound private result, and never POSTs a summary. `HAFNIA_GW_PASSWORD` is ignored. Preflight and `--apply` cannot be combined.

Installed gateway documentation and generated UI client identify `GET /api/System/Information` and `QuotaInformation.DailySummaryCount`, `DailySummaryQuota`, and `DailySummaryReset`. [quota-contract.json](quota-contract.json) records the verified schema; unexpected live values block submission. The UI explicitly says these counts apply to this gateway, not all potential account clients. No global usage claim is made.

Runner cap remains 480, gateway headroom 20, concurrency one, A/B/C ceilings unchanged. Source coverage proof must be refreshed within 15 minutes of submission. Zero claims exist in both the superseded and fresh ledgers. The successful offline, authenticated, quota and coverage preflights are recorded in [fresh-preflight.json](../../../results/reliability/fresh-preflight.json). Validation: 17 runner tests plus four parser-recovery tests pass; live submission behavior is untested.
