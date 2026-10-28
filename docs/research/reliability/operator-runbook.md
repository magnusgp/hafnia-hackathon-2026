# Historical first-batch plan: superseded for execution

The October 22 intervals below are expired and must not be submitted. The [fresh preflight report](fresh-preflight.md) records the replacement sources, unchanged four prompts/IDs, successful authenticated preflight and current execution instructions. Original historical evidence remains unchanged.

Password fix: **completed, reported by the operator**. Authentication validation is reserved for the operator's separate PowerShell session. The agent has not retried login and will not submit summaries. Linux SSH access and the A10G are already verified; the earlier remote Python quoting error was separate from authentication.

The first batch is Stage B, one request per new prompt/scene cell. Stage A reuses all 16 saved assessments. No stability repeats or new controls are included in this batch. Further repetitions are conditional on a useful diagnostic question, not automatic budget consumption.

| Experiment ID | Original recording interval, UTC on 22 October 2026 | New calls |
|---|---|---:|
| `REL26-B-railway-v3-r01` | 11:03:39–11:03:52 | 1 |
| `REL26-B-railway-v4-r01` | 11:03:39–11:03:52 | 1 |
| `REL26-B-gate-v3-r01` | 11:04:39–11:04:52 | 1 |
| `REL26-B-gate-v4-r01` | 11:04:39–11:04:52 | 1 |

Expected new requests: **4**. Actual submissions this session: **0**. Concurrency: **1**. Daily cap: **480**. These are four assessments of two existing source loops, not four independent events. Exact prompt bodies and the shared JSON suffix are frozen in [first-batch-matrix.json](first-batch-matrix.json). The generator materializes the full prompt, exact private camera URI, source-manifest hash, review hash and experiment ID into each private plan entry.

Railway v3 names the red-clothed person and explicitly makes seated-edge contact ambiguous; v4 asks for chronological review. Gate v3/v4 ask about visible handling without requiring successful opening. Unlike the original v1/v2 task, they do not require establishing a tool. Any change in decision therefore mixes prompt framing with a broader action definition; it is not a controlled estimate of improvement on the original tool-specific task.

Both historical intervals are 13 seconds. Gate ends before the sampled reset uncertainty at 11:04:52.865–53.865. Sampled continuity is reviewed; uninterrupted full-motion continuity remains unverified. Original recordings may be outside retention. If unavailable, **zero** of these historical requests should execute. Reacquired loops need new source/review versions and experiment IDs; they retain the same event-family identity and are not independent events. Do not edit this frozen plan to point at later timestamps.

## Offline preparation and preview

These commands perform no authentication or network requests:

```powershell
.venv/Scripts/python.exe scripts/reliability_plan.py --root runs/reliability-20261026 --responses C:/Users/Administrator/adaptive-watch-private/hafnia-16
.venv/Scripts/python.exe scripts/reliability_runner.py --root runs/reliability-20261026/operator-batch --plan runs/reliability-20261026/first-batch.private.json --review runs/reliability-20261026/review-signoff.json
```

The preparation verifies the frozen definition/review hashes, all 87 reviewed frame files and timestamps, original railway MKV hash, all 16 original response-file hashes and request hashes/prompts/URIs, and distinct saved summary IDs. Original response-file hashes are locked privately for subsequent verification. It retains the original manifests, including gate frames whose hashes were first recorded in the frozen review rather than in the acquisition manifest. Preview currently validates all four planned experiments. The persistent ledger is empty. Sanitized verification is in [first-batch-readiness.json](../../../results/reliability/first-batch-readiness.json).

## Operator execution gates

After separately confirming authentication, the operator may run the preview command with `--apply --operator-auth-confirmed --quota-contract PRIVATE_PATH --recording-availability PRIVATE_PATH`. This document prepares that command; it does not authorize the agent to run it now. The runner reads the password only from the user-opened terminal and ignores `HAFNIA_GW_PASSWORD`.

The quota contract must come from the installed gateway documentation: read-only endpoint, remaining/limit/day fields and `verified_from`. It remains unverified, so no fabricated example balance or guessed endpoint is supplied. The runner requires live limit=500, current UTC quota day and more than 20 requests remaining before each new submission. Adapt and test the contract if the actual gateway reset convention differs.

The recording-availability JSON has a `recordings` list. Each source record needs `event_id`, `manifest_sha256`, `available: true`, `checked_by`, `checked_at`, `coverage_start`, `coverage_end`, `evidence_file`, and `evidence_sha256`. Preserve actual read-only recording-coverage output or an operator inspection record as the hashed private evidence. The check must cover the exact requested UTC interval and be at most 15 minutes old. A saved local MKV alone does not prove the gateway can retrieve an expired XProtect URI.

Retain this one ledger root. A timeout resumes its summary ID. An ambiguous POST blocks new reservations and must be reconciled against exact prompt/URI history; never delete claims to retry. Terminal transport, formatting, semantic and uncertain outcomes remain separate. No PromptId or dispatch API is used.

## Negative-control selections

| Candidate | Evidence period | Use / exclusion |
|---|---|---|
| Railway platform approach | 11:03:39.013–41.513, six samples | Task-matched frame negatives; 2.5-second span, too short for the current 12–17-second contract. Zero new calls. |
| Railway seated edge / descent transition | 11:03:42.013–48.013, thirteen samples | Ambiguous, never a negative control. |
| Railway far-platform exit | 11:03:51.013–51.513 | First sample ambiguous; last negative. Insufficient duration for inference. |
| Gate departure | 11:04:49.865–52.865, four samples | Task-matched sampled negatives; 3-second span, followed by reset uncertainty. Do not extend through a loop. |
| Busy street | Four saved task assessments of one source loop | Reuse as domain-mismatched controls; not hard-negative evidence. Zero new calls. |
| Open-lane traffic | Existing source repeats in roughly eight seconds | Cannot make a continuous 12–17-second negative; excluded. |

No eligible distinct task-matched negative event has been established. Stage C therefore has zero committed requests. Seek distinct footage of people remaining on platforms and people legitimately near a gate without manipulation; label only visible behavior, not authorization or intent. Shorter intervals remain unsupported by verified evidence and are not manufactured.

## Existing Linux evidence: timing result

Pinned Faster R-CNN ResNet50 FPN v2 / COCO_V1, person threshold 0.5, unchanged weights hash and ten track hypotheses are preserved in [saved-analysis.json](../../../results/reliability/saved-analysis.json). Re-scoring requires no new GPU inference. The original polygon and narrowed v3 both first flag at 11:03:44.513, **3.5–4.0 seconds before** established entry at 48.013–48.513. Both flag 0/6 clear pre-entry negatives, 8/13 ambiguous pre-entry samples and 5/5 clear post-entry samples. The rejected wider polygon flags 6/6 clear pre-entry negatives and starts 9–9.5 seconds early. V3 repairs platform inclusion but does not solve seated-contact timing. All frames remain calibration; no threshold search, track merging, new training or held-out accuracy claim was introduced.

Validation: 13 runner safety/recovery tests and four parser-recovery tests pass. The offline plan generator and runner preview were executed successfully; no live runner behavior is claimed.
