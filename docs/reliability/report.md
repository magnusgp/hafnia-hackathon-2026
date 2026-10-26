# Reliability evaluation — 26 October 2026

**Provisional NO-GO for independent AI verification as the hackathon flagship.** The saved evidence supports investigating Hafnia contradictions, but does not establish that the CV verifier improves reliability. The proposed geometry revision introduces clear negative-frame flags. Human label confirmation, live gateway access and Linux authentication remain unresolved. This is an interim evidence report, not a completed large evaluation.

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

The twelve incident requests cover at most six distinct source event loops. Two prompts on one loop are repeated assessments, not independent events. The four controls share a seventh source scene. The gate contact sheet visibly repeats; the first reset candidate is bracketed by samples 14–15. No new continuity claims have been made for unsampled video. Gate review has timestamped snapshots but no saved original MKV; railway has an original MKV and hash-checked snapshots. Full-motion playback and human review remain necessary.

For the matched railway interval, 11:03:39–11:03:52 UTC on 22 October, both saved decisions deny track-area descent. The reviewed sampled sequence shows clear standing track-bed entry by 11:03:48.513, with a transition bracket starting at 48.013. This agrees with the user's previously confirmed visible descent and entry, and contradicts the two model decisions. The new frame-level labels are explicitly AI-assisted drafts awaiting human confirmation. The two gate responses describe manipulation while deciding `not_observed`, although the prompt asks about manipulation rather than successful opening. This is an internal evidence/decision contradiction under the original task definition. It does not establish tool identity, opening, forced entry, authorization or criminal intent.

| Railway sampled frame category (draft) | Samples | Original polygon flags | Previously revised polygon flags |
|---|---:|---:|---:|
| Clear pre-entry negative | 6 | 0 | 6 |
| Seated / transition ambiguous | 13 | 8 | 13 |
| Clear post-entry positive | 5 | 5 | 5 |
| Far-platform exit unreviewed | 2 | 0 | 2 |

These are scene-level “any detected person footpoint in polygon” flags, not verified target-person tracks or physical occupancy. The original proxy first flags at 44.513, 3.5–4 seconds before clear entry; that period is ambiguous and must not be counted as proven false occupancy. The previous revision flags all six clear negative samples, including background/platform detections: reject that revision as an operational entry rule. Neither polygon is a validated verifier. The same frames informed geometry calibration; the table is a retrospective diagnostic, not held-out performance. No new thresholds were tuned. Track fragmentation, original boxes and all association hypotheses remain in the private CV audit. The existing pinned Faster R-CNN artifact was reused and bound to the exact manifest hash. No new Linux inference or model training occurred.

CV offers timestamped localization that exposes a meaningful disagreement with Hafnia, but added *reliability* remains unproven. There are no evaluated genuine hard-negative events or independently held-out entry events. Geometry repair needs calibration frames separated from evaluation frames or, preferably, distinct source footage; reserve new footage before choosing thresholds. No accuracy improvement or validated failure rate is claimed.

Live blockers: the configured local gateway password returned HTTP 401; the reachable Linux host rejected SSH public-key authentication. Credentials were not printed or changed. Gateway quota endpoint/schema and short-interval support could not be verified. Existing 12–17 second request validation is a client restriction, not proof of the server's minimum duration. Do not fabricate short clips or replace expired source intervals with later repetitions. No service, network, firewall, account, native event or alarm operation was performed.

The new private runner is staged but has not been exercised against the live gateway. It defaults to 480 daily requests, uses one request in flight, enforces A/B/C caps of 128/192/144, checks a documented live quota contract before every POST, retains 20 requests of gateway headroom, freezes the plan, persists claims before POST and requires exact-payload reconciliation of ambiguous IDs. Human review and quota-schema checks fail closed. A single durable ledger root must be retained across days and stages. Prior responses should be omitted from new-submission plans and referenced through the offline audit; the runner does not automatically discover all historical ledgers. Deploying multiple unrelated runners would violate that operating assumption.

To resume: confirm the private timestamped labels, restore the already-authorized gateway/SSH authentication through existing configuration, verify the installed quota schema, then materialize only useful experiments from [protocol.md](protocol.md). Reconsider GO only after corrected geometry succeeds on independent entry footage and task-matched negatives without hiding pre-entry flags.
