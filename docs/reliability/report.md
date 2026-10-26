# Reliability evaluation — 26 October 2026

**Provisional NO-GO for independent AI verification as the hackathon flagship.** The saved evidence supports investigating Hafnia contradictions, but does not establish that the CV verifier improves reliability. The previous geometry revision introduces clear negative-frame flags. A narrower image-reviewed track-bed polygon removes those flags on calibration frames, but seated-edge ambiguity remains. AI demo labels are now frozen with explicit user authorization; live gateway authentication remains unresolved. This is an interim evidence report, not a completed large evaluation.

Sixteen saved requests were reused; zero new inference requests were sent. Original response files remain untouched outside Git. Private audit files preserve exact prompts, responses, source hashes, frame timestamps and track IDs. Sanitized counts are in [saved-analysis.json](../../results/reliability/saved-analysis.json). The standalone [comparison.svg](comparison.svg) is suitable for a short presentation comparison without private imagery.

| Incident camera | v1: supported / not observed / uncertain | v2: supported / not observed / uncertain |
|---|---:|---:|
| Vehicle / queue | 1 / 0 / 0 | 1 / 0 / 0 |
| Bin tipping | 1 / 0 / 0 | 1 / 0 / 0 |
| Scooter placement | 1 / 0 / 0 | 1 / 0 / 0 |
| Gate manipulation | 0 / 1 / 0 | 0 / 1 / 0 |
| Railway entry | 0 / 1 / 0 | 0 / 1 / 0 |
| Graffiti | 1 / 0 / 0 | 1 / 0 / 0 |

Four additional v1 requests apply railway, gate, graffiti and vehicle tasks to one busy-street control: all returned `not_observed`. Those four requests are neither four independent events nor task-matched hard negatives. Total: eight supported, eight not observed, zero uncertain, zero gateway failures and zero unrecoverable formatting errors in the saved set. Compatibility normalizations remain disclosed per response; valid parsing does not establish strict formatting compliance. Selection of this saved set prevents any general failure-rate estimate.

The two prompt variants are exactly the existing `adaptive_watch.evaluation.prompt` definitions: v1 starts “Assess whether the following action is directly visible:”; v2 starts “Review the visible action sequence and decide whether this event is supported:”. Both use the same scene-specific visible-action definition, camera-name exclusion, four-field JSON schema and instruction against inferring intent. Exact full prompts are preserved privately and in the existing reproducible prompt function. Counts above include every evaluated variant; no new variants were evaluated.

The twelve incident requests cover at most six distinct source event loops. Two prompts on one loop are repeated assessments, not independent events. The four controls share a seventh source scene. The gate contact sheet visibly repeats; the first reset candidate is bracketed by samples 14–15. No new continuity claims have been made for unsampled video. Gate review has timestamped snapshots but no saved original MKV; railway has an original MKV and hash-checked snapshots. Full-motion continuity remains unverified. The user authorized AI review for this demo; the private reviewed artifact and hash-bound signoff preserve that scope without claiming human attestation.

For the matched railway interval, 11:03:39–11:03:52 UTC on 22 October, both saved decisions deny track-area descent. The reviewed sampled sequence shows clear standing track-bed entry by 11:03:48.513, with a transition bracket starting at 48.013. This agrees with the user's previously confirmed visible descent and entry, and contradicts the two model decisions. Frame-level labels were frozen as AI-reviewed for the demo after source-sheet and selected full-resolution inspection; they are not independently adjudicated human labels. The two gate responses describe manipulation while deciding `not_observed`, although the prompt asks about manipulation rather than successful opening. This is an internal evidence/decision contradiction under the original task definition. It does not establish tool identity, opening, forced entry, authorization or criminal intent.

| Railway sampled frame category (AI demo review) | Samples | Original | Rejected revision | Track-bed v3 |
|---|---:|---:|---:|---:|
| Clear pre-entry negative | 6 | 0 | 6 | 0 |
| Seated / descent ambiguous | 13 | 8 | 13 | 8 |
| Clear post-entry positive | 5 | 5 | 5 | 5 |
| Far-platform exit transition, ambiguous | 1 | 0 | 1 | 0 |
| Established far-platform presence, negative | 1 | 0 | 1 | 0 |

These are scene-level "any detected person footpoint in polygon" flags, not verified target-person tracks or physical occupancy. The original and v3 proxies flag at 44.513, 3.5-4 seconds before clear entry; that period is ambiguous and must not be counted as proven false occupancy. The rejected revision flags all six clear pre-entry negatives and the far-platform negative. The [v3 geometry](railway-geometry-v3.json) excludes the opposite platform using visible image boundaries and retains zero flags on seven clear negatives and five flags on five clear entry samples. It still flags eight ambiguous seated samples, so it is a review candidate generator, not a validated entry rule. No claim of improved timing is justified.

All 26 frames are explicitly calibration data; v3 was pinned before rescoring, without a parameter search. No held-out performance is claimed. The detector threshold stays 0.5. Track fragmentation, original boxes and association hypotheses remain in the private audit. The pinned Linux Faster R-CNN artifact was reused and bound to the exact manifest hash. No new inference or model training occurred.

CV offers timestamped localization that exposes a meaningful disagreement with Hafnia, but added *reliability* remains unproven. There are no evaluated genuine hard-negative events or independently held-out entry events. Geometry repair needs calibration frames separated from evaluation frames or, preferably, distinct source footage; reserve new footage before choosing thresholds. No accuracy improvement or validated failure rate is claimed.

Live blockers: the configured local gateway password returned HTTP 401; the documented existing SSH identity successfully authenticated to p022-linux, where a read-only query confirmed NVIDIA A10G. The live Linux checkout is e253b64918a0a7208ac76bfe28cedaca79b36d3c with untracked detector/tracker scripts; it was preserved unchanged and is distinct from the saved artifact revision. Credentials were not printed or changed. Gateway quota endpoint/schema and short-interval support could not be verified. Existing 12–17 second request validation is a client restriction, not proof of the server's minimum duration. Do not fabricate short clips or replace expired source intervals with later repetitions. No service, network, firewall, account, native event or alarm operation was performed.

The new private runner is staged but has not been exercised against the live gateway. It defaults to 480 daily requests, uses one request in flight, enforces A/B/C caps of 128/192/144, checks a documented live quota contract before every POST, retains 20 requests of gateway headroom, freezes the plan, persists claims before POST and requires exact-payload reconciliation of ambiguous IDs. The runner accepts either human review or explicitly authorized AI demo review, and quota-schema checks fail closed. Pending summaries now block further reservations across restarts; summary identity and source-frame hashes are verified. A single durable ledger root must be retained across days and stages. Prior responses should be omitted from new-submission plans and referenced through the offline audit; the runner does not automatically discover all historical ledgers. Deploying multiple unrelated runners would violate that operating assumption.

To resume: use the frozen private AI demo review, restore gateway authentication through existing configuration, verify the installed quota schema, then materialize only useful experiments from [protocol.md](protocol.md). Reconsider GO only after corrected geometry succeeds on independent entry footage and task-matched negatives without hiding pre-entry flags.

Verification of this follow-up: all 10 runner safeguards and all four response-recovery tests pass. Gateway login was rechecked and returned HTTP 401. Zero inference requests were sent.
