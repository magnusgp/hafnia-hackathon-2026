# REL26-D diagnostic preparation

No new inference was submitted. The precise, frozen [24-request matrix](diagnostic-24-matrix.json) replaces the earlier unexecuted four-request proposal; it does not authorize execution. Source-bound private plan, new review, empty persistent ledger and rejected acquisition remain under `runs/reliability-diagnostics/`. Historical plans, predictions, responses and accepted annotations were not edited.

## Eight-request audit and model identity

[Sanitized audit](../../results/reliability/eight-request-audit.json) records all eight exact prompts, summary IDs, payload hashes, URI hashes, camera-path hashes, requested UTC intervals, source-manifest/video hashes where available, returned metadata and parser results. Historical gate sources have reviewed snapshots and manifest hashes but no recorded MKV digest; that missing provenance is explicit as null. Full original payloads and responses remain private. All 16 historical saved response files passed their original hash checks. All eight prompt and URI lists exactly match their returned `Request` fields.

All eight actual payloads contain `Prompt` and `VideoUris`, without `PromptId` or an explicit model selection. All eight returned `Request.AiModelId` values are **`traffic-general`**. All report `Source.Trigger: Manual` and `Progress: Completed`. Transport HTTP status, backend weights/version, system prompt, sampling schedule, fetched video digest and model-consumed frames are not recorded. Completed status and echoed source URIs establish neither which frames were decoded nor their delivery to the model. Returned `Source` is trigger metadata, not independent recording provenance.

| Scene | v1/v2 UTC interval on October 22 | v3/v4 UTC interval on October 26 |
|---|---|---|
| Railway | 11:03:39–11:03:52 | 22:03:53–22:04:06 |
| Gate | 11:04:39–11:04:52 | 22:03:51–22:04:03 |

Model alternatives are **not currently verified**. Installed `Hafnia.Vlm.Gateway.xml` documents `ModelsController.GetModelsAsync` as retrieving supported models from the configured VLM. Installed `wwwroot/site/search.json`, SmartClient Generate section, describes selection but says the default traffic model was the only option when written. A single anonymous read-only `GET /api/Models` on October 27 returned HTTP 401; no login was attempted and no environment password used. That is an authorization failure for discovery, not evidence that alternatives exist or do not exist. A successful authenticated model-list read remains required before execution. The matrix holds the observed model constant; no model-switching factor or unsupported alternate model is invented.

The evidence currently permits three unresolved explanations: source retrieval/sampling differences; person/object/spatial recognition errors; and task/decision interpretation sensitivity. Gate v1/v2 describe manipulation but apparently require successful opening for a positive decision. Gate v3/v4 deny handling itself. Railway v1–v4 deny the reviewed transition. Different historical intervals prevent attributing these changes solely to prompts. The new design probes these layers separately; it cannot reveal internal reasoning or prove source delivery from prose alone.

## Precise design: 24 requests

IDs are `REL26-D-{scene}-{family}-r{01|02}`, with `scene` exactly `railway` or `gate`. The JSON contains all 24 explicit IDs, full verbatim prompts including their common evidence-only suffix, SHA-256 prompt hashes and fixed order. Each row below expands to four calls: two scenes, two exact repetitions. Run all first repetitions before the second block, interleaving railway/gate within each family. Hold source URI and prompt identical within each repetition pair; do not add conversation history. No controls or additional variants are counted.

| Family | Railway question | Gate question | Calls |
|---|---|---|---:|
| `open` | Neutral setting, people and actions | Same neutral description | 4 |
| `inventory` | People/clothing/posture and visible objects | Same inventory, unresolved contacts allowed | 4 |
| `sequence` | Start, intermediate posture/contact/height and end | Same chronological sequence | 4 |
| `direct` | Visible movement down from platform into track area: yes/no/unknown | Visible handling at gate/latch: yes/no/unknown; opening unnecessary | 4 |
| `spatial` | Main person's clothing; platform top/edge/bed relationship; lower limbs | Main person's clothing; hand/contact location; object identity unknown if unresolved | 4 |
| `separate` | Approach, sitting, downward transition and subsequent occupancy assessed separately | Approach, crouch, contact, gate movement and opening assessed separately | 4 |
| **Total** | **12** | **12** | **24** |

Read each response first for setting recognition, relevant-person recognition, identifiable objects, temporal order, contact/depth visibility and action evidence. Preserve literal text and quotations supporting each assessment. Omission is unknown, not a negative. Record explicit denials separately from absent descriptions. For the gate, keep handling, tool identification, opening and inferred intent separate. For railway, keep edge proximity, descent and subsequent track occupancy separate. Exact repetitions estimate within-source output variability only; they add no independent events. Do not call prose a formatting failure because it lacks the former incident JSON schema.

Use concurrency one, the existing 480/day cap and 20-request gateway headroom. A separate empty persistent ledger is prepared at `runs/reliability-diagnostics/operator-batch/reliability-ledger.sqlite3`; use it for every resume of this batch. Preserve the frozen plan hash and each exact payload, ground-truth reference, raw response, summary ID, actual returned model and parse/review status. Commit an ambiguous claim before POST; reconcile exact prompt/URI to an existing summary ID rather than retry. Never reuse the completed REL26-B experiment IDs. The audit exposed a reconciliation defect: the runner compared top-level fields although all eight saved responses nest them in `Request`. This comparison is corrected and tested, including rejection of misleading top-level echoes. Before execution, adapt the legacy incident parser for diagnostic prose. This batch is deliberately not submission-ready.

## Fresh recording verification

Read-only XProtect acquisition on October 27 obtained two one-minute exports and selected whole-second intervals below. No clips were fabricated, stretched or concatenated. [Verification results](../../results/reliability/diagnostic-recording-verification.json) contain full manifest and MKV SHA-256 hashes. Every saved snapshot hash, selected export hash, source/review binding, under-24-hour age and 12–17-second contract passed offline validation across all 24 definitions. A subsequent read-only exact camera/GUID sequence query verified coverage for both sources and passed the runner's availability checks for all 24 definitions.

| Scene | Date | Actual UTC interval | Snapshots | Decoded export frames / PTS |
|---|---|---|---:|---|
| Railway | 2026-10-27 | 11:55:38–11:55:51 | 26 | 130 / 0.1–13.0 s |
| Gate | 2026-10-27 | 11:55:49–11:56:02 | 26 | 140 / 0.0–13.9 s |

AI demo review inspected every decoded frame in chronological sheets and selected full-resolution action/contact frames. Both accepted exports show coherent progression without a reset. Railway snapshots show descent at 11:55:48.013 and clear track-area presence at 48.513. Gate shows approach, contact/handling near the chained gate and crouching; successful opening and intent remain unestablished. These are new, separately stored AI review records, not a claim of human attestation or an alteration of the accepted reference. The fresh railway MKV SHA-256 is exactly identical to the October 26 v3/v4 export (`c3ed451c…c24e23b`), confirming duplicate exported video content despite different source UTC bounds. This is useful for a paired prompt diagnostic, never an independent new event.

The first gate candidate, 11:55:41–11:55:54, was rejected: full-resolution samples show the person disappearing between 48.465 and 48.965. It remains unchanged. The accepted gate starts after that boundary. The railway next-reset bracket is 11:55:52.313–52.813, after its selected end. Gate export PTS span exceeds the requested interval by 0.9 seconds; absolute PTS origin/export preroll remains unverified. Do not assign UTC to decoded frames by adding PTS to the requested start. Timestamped snapshots and requested URI bounds establish the local source identity, not gateway-internal frame delivery.

Earliest source expiry is **October 28, 11:55:38 UTC**. This is a preparation-time verification, not evergreen submission approval. Recheck authentication, model availability and live quota; refresh exact coverage within 15 minutes of submission and enforce age at each POST. If expired, acquire/review a new versioned source binding; keep these definitions and original records intact.

## Pose and geometry assessment

The original CV evidence is unchanged: its first polygon positive occurs 3.5–4 seconds before confirmed entry. A seated box-bottom proxy moves about 1.03 pixels horizontally and 15.29 vertically; the new point is only 0.173 horizontal pixels beyond the polygon boundary. The unchanged near-edge geometry and posture-sensitive box bottom explain the early flag. It is a proximity warning, not track entry.

Better region geometry should separately represent platform top, vertical face and visible track bed, following physical scene boundaries rather than moving a threshold to match entry time. A 2D footpoint cannot alone establish ground contact or depth near an occluding edge. Preserve separate outputs: proximity candidate; visible downward transition; confirmed occupancy evidence; unknown contact. Keep original fragmented track identities and missing detections.

Pose is a plausible calibration experiment, not a demonstrated repair. Pretrained Torchvision Keypoint R-CNN provides person boxes and 17 body keypoints, including lower limbs ([official implementation](https://github.com/pytorch/vision/blob/main/torchvision/models/detection/keypoint_rcnn.py), [output contract](https://docs.pytorch.org/vision/0.18/models/generated/torchvision.models.detection.keypointrcnn_resnet50_fpn.html)). A future Linux-only ablation could pin `KeypointRCNN_ResNet50_FPN_Weights.COCO_V1`, library versions and checkpoint hash, and compare ankles/knees/hip motion against the saved detector boxes. It has not been downloaded or run in this task. Seated limbs, partial occlusion and perspective make predicted keypoints insufficient evidence of physical contact; confidence/visibility and temporal uncertainty must be retained.

First annotate physical edges and limb visibility without seeing candidate predictions. Then freeze geometry, uncertainty treatment and any persistence thresholds on calibration only. Compare box-bottom geometry, revised physical regions and pose-assisted transitions on separately reserved distinct footage. Reacquiring this same loop is still calibration, not an independent test. No new training, threshold optimization or accuracy improvement is claimed.

## Distinct footage and controls

The refreshed read-only catalog still contains 11 cameras. Local manifests include railway, gate, bin, scooter, graffiti, street/traffic, vandalism and breakdown scenes. For the two current tasks there are **two known positive loop families**, **zero additional verified distinct positive events**, and **zero eligible distinct task-matched negatives**. Fresh October 27 captures are visibly the same railway and gate loops as before. The other incident scenes may support their own tasks but are not controls for platform descent or gate handling. Catalog names alone cannot prove absence of relevant action in all historical footage; that wider archive has not been exhaustively reviewed.

Missing controls: independent platform-only walking/standing, seated edge without descent, gate approach without handling, handling without opening, and separate true entry/handling events. Existing short approach periods cannot be extended to coherent 12-second negatives without including action or a reset. No empty-looking frames or loop copies are promoted to independent negative clips. Expected diagnostic requests remain **24**, control requests **0**. Submission remains **NO-GO pending explicit authorization and the execution gates above**.

Reproduce offline: `scripts/reliability_diagnostic_prepare.py`, then `--bind` while sources remain eligible. Source review sheets use `--sheets` and the existing private pinned decode dependencies. `--models` performs one anonymous read-only model-list query; it never logs in. Exact coverage can be refreshed using `scripts/reliability_availability.ps1 -EvaluationRoot runs/reliability-diagnostics -PlanPath runs/reliability-diagnostics/execution-plan-v1.private.json`. No inference command is provided for this unapproved batch.
