# Adaptive Watch initial hybrid milestone — 2026-10-22

Phase 2 has a minimal, measured railway proof of concept. **Phase 1 is incomplete:**
gateway authentication was unavailable, and the operator explicitly deferred the
password fix to the next session. No Hafnia requests were submitted, no native
events were generated, and no VMS configuration was changed. The 40-request
authorization remains unused. Do not describe this milestone as a validated hybrid detector.

The operator's prior integration results are accepted: all 11 cameras, coherent
15-second vandalism analysis, gateway-rule alarms, direct XML HTTP 200 with native
Smart Client alarm ID 3, real MKV export, private SCP, DINOv2 CUDA inference, and
SSH with the dedicated identity. These were not repeated as infrastructure tests.
The fog classifier's preregistered superiority gate **failed**; its results remain unchanged.

## Six-scene evaluation status

Recent XProtect recording sequences and timestamped snapshots were acquired for
all six scenes. Manual contact sheets were used to select 12–13-second intervals
within one loop. A continuous recording sequence alone does not prove loop continuity.
The observations below are manual recording inspection, **not Hafnia findings**.

| Scene | Visible recording observation | Hafnia result |
| --- | --- | --- |
| Vehicle and queue | Pickup stops, visible smoke, another vehicle queues, person exits | Not submitted |
| Bin | Person tips green bin onto sidewalk and walks away | Not submitted |
| E-scooter | Rider dismounts, leaves scooter lying across sidewalk | Not submitted |
| School gate | Person manipulates gate/lock area with a tool at night; successful entry unestablished | Not submitted |
| Railway | Red-jacketed person sits at edge, descends and moves across track area | Not submitted |
| Graffiti | Person moves arm/spray against standing train; new colored markings appear | Not submitted |

Private plan: `runs/hybrid/plan.json`, 16 requests: two short prompt versions per
new scene and four original `busy_street` negative controls. Those controls are
domain-mismatched and do not measure hard-negative discrimination. The original
open-lane traffic recording visibly loops in roughly eight seconds, so it cannot
satisfy the required continuous 12–17-second interval and was excluded. The busy
street interval was manually inspected for continuity. Add a relevant, genuinely
continuous road control when available; do not silently cross a loop boundary.

No reliability, prompt-stability, accuracy or CV-over-Hafnia superiority claims
can be made until actual gateway results are collected. Repeated loops are the
same synthetic scene, not independent examples. All private intervals, GUIDs,
source manifests, hashes and prompt previews are in ignored `runs/` files.
These recordings expire after 24 hours: reacquire and review if the next session
falls outside that retention window.

## Provisional railway CV selection and measured result

Railway is provisional because image-space people/zone positions and sampled
durations are concrete local measurements. Final selection still depends on Phase 1.

Both GPU runs used **host `p022-linux`, NVIDIA A10G (23,028 MiB)**. The first run
used base revision `e253b64918a0a7208ac76bfe28cedaca79b36d3c` with explicitly hashed
new scripts. The reproducibility run used clean, isolated implementation revision
`1163ddf94ef7252b8a41563c8ed5e2b46a925612`. Publishing through the GitHub connector
may give an equivalent source tree a different commit identity; the reported run
revision is the actual local Git revision at execution, not an invented remote SHA.

- PyTorch `2.5.1+cu124`, torchvision `0.20.1+cu124`, pretrained Faster R-CNN
  ResNet50 FPN v2 `COCO_V1`; person class, score threshold 0.5.
- Weights SHA-256: `dd69338a24b8d7381807e247652bdc356325bcbaf1cd3e092e00e0a1a58706bf`.
- Runner SHA-256: `9ee7c70ac61938cba3269dfcc98faed25c04089ff935f4272bbaebd163f670dd`.
- Tracker SHA-256: `864a08c1fa742ee48e736e01b55ab37f7892498c7c84487ad423d873a342618b`.
- 26 server-timestamped JPEGs at approximately 2 Hz from one coherent 13-second
  recording. Per-frame hashes verified. Normalized bounding boxes and scores saved.
- Exact-commit runtime: **54.51 ms/frame detector mean**, **54.58 ms p95**,
  **2.36 s processing**, **0.76 s cached model loading**, **673.43 MiB peak
  allocated CUDA memory**. Processing includes warmup, decoding JPEGs, detector,
  tracking and baseline; acquisition, transfer and model loading are excluded.
- Initial run: 54.49 ms/frame, 2.45 s processing. This is repeatability on one
  recording, not independent evidence of accuracy or multi-camera capacity.
- Track hypothesis 7: 19 observations; 0.5-second zone-entry bracket;
  **6.0 seconds of consecutive in-zone sample pairs**; normalized image-plane
  path length 0.872; minimum detector score 0.998 (not calibrated confidence).
  Ten track hypotheses in total include transient detections and fragmentation;
  they are not a count of ten distinct people.

The draft polygon is developer-defined and requires operator review. Visual box
inspection shows the box-bottom proxy entering it while the person is still
seated at the edge, before clear descent. Thus 6.0 seconds is **geometric proxy
occupancy**, not verified time physically standing on tracks. The tracker also
fragments the foreground person during the initial approach. No interpolation
across missing observations, metric-world distance, intent, or identity is claimed.

Model reference: [torchvision 0.20 detector documentation](https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.detection.fasterrcnn_resnet50_fpn_v2.html).
This is **pretrained inference plus handwritten geometry and tracking**, with no
custom neural training. No independent labeled dataset was established to justify
a supervised experiment. The scene cannot serve as both training and validation data.

## Concrete local capability and baseline comparison

The output supplies timestamped person boxes, track hypotheses, image-space motion,
zone membership and entry brackets, which can be overlaid on the original recording
and audited. Hafnia-only comparison remains unrun, so a measured improvement over
Hafnia cannot yet be asserted.

The simple baseline measures the fraction of zone pixels whose grayscale value
changes by more than 25/255 between samples. It takes **10.25 ms/frame**. Across
25 successive comparisons, a fixed 1% changed-pixel threshold fires on all 25:
13 have a detected person in the zone, 12 do not. Motion-change ranges overlap:
8.78–22.43% with a detected person and 7.76–22.33% without one. These are comparisons
against detector observations, **not labeled precision/recall**. They illustrate
why undifferentiated motion does not supply person localization. The scene is
synthetic, with background variation; no baseline threshold was tuned on it.

Private artifacts: `runs/hybrid/railway-cv-1163ddf.json`, matching `.jpg` overlay,
`railway-export-audit.json`, and `evidence-incomplete.json`. The evidence explicitly
contains `hafnia: null`, `combined_decision: incomplete_evidence`, and no event metadata.

## Provenance and status corrections

Acquisition now rejects intervals not covered by a recording sequence and records
sequence coverage, UTC camera timestamps, per-frame hashes, and MKV hash/requested
interval. A recording sequence is source identity/coverage, not an immutable
evidence-lock identifier. No evidence lock or recording configuration is created.

The selected MKV has 130 decoded frames: first PTS 0.1 s, last PTS 13.0 s, PTS span
12.9 s. Requested duration is 13.0 s. PTS does not independently establish absolute
first-frame UTC. CV therefore uses server-timestamped snapshots; no absolute MKV
alignment is claimed. `aw.py footage --end` now keeps supplied requested end
separate from decoded last timestamp; missing requested end remains unknown.

Failed gateway analyses retain `LastError`, fail strict assessment and cannot
become a successful positive. The evidence join requires matching camera, exact
UTC interval, inline prompt, gateway request and source-manifest hash. Unknown or
discordant evidence remains incomplete/uncertain. No output alone establishes fact.

## Validation and next session

Windows: 83 tests run, 17 optional-dependency skips. Linux at implementation
revision `1163ddf`: **83 tests pass, no skips**, including real AnalyticsEvent XSD
validation with `lxml==5.3.0`. Windows golden XML line endings are pinned to LF.

1. After the operator's deferred authentication fix, reacquire recordings if older
   than 24 hours; inspect loop boundaries and freeze the plan. On Windows run
   `.venv\Scripts\python.exe scripts/adaptive_watch/evaluate.py runs/hybrid/plan.json`
   for preview, then the same command with `--apply`. Use the same ledger root
   across batches: it caps this assignment at 40 **attempted** submissions.
   Submit no `PromptId`. A timeout/ambiguous submission is claimed persistently;
   reconcile History rather than retry. Poll an existing summary ID instead.
2. Review actual per-scene outputs, strict parse failures and both prompt versions.
   Revisit primary scenario choice. Use a small number of genuinely relevant
   controls within the remaining budget; report scene behavior, not inflated accuracy.
3. Process the exact railway interval sent to Hafnia with the pinned CV runner.
   Operator reviews/defines the track polygon. Address seated-footpoint bias,
   verify identity associations and label a short before/edge/track sequence for
   timing error assessment. Compare sampled occupancy and motion baseline with
   those manual observations; keep tuning examples separate from validation.
4. Join the two evidence records using `adaptive_watch.evidence.join_evidence`.
   Preserve exact prompt, summary ID, raw response, parsed outcome and limitations.
   Candidate-for-review status is not event authorization.
5. Propose a distinct event such as `Adaptive Watch Railway Review` with the
   railway camera as source. Obtain explicit approval before creating any new
   analytics event definition or alarm. Do not reuse the property-damage event.
6. Reuse the existing XML serializer, digest approval, persistent dispatch ledger
   and duplicate suppression. Present the camera/recording, CV evidence, Hafnia
   assessment, proposed event/source and **exact XML bytes plus SHA-256**.
   **Stop for explicit human approval before the first hybrid event send.**
   No eligible payload can be produced yet because Hafnia evidence and the new
   event definition are absent.
7. After approval, send once via the verified localhost Event Server route and
   verify the resulting camera, event and native alarm ID in Smart Client.
   HTTP 200 alone remains transport acceptance, not native-alarm verification.

Linux reproduction (from an isolated checkout, using the existing ML environment):

```bash
~/.local/bin/uv pip install --python ~/hafnia-hackathon-2026/.venv/bin/python torchvision==0.20.1 --no-deps
~/hafnia-hackathon-2026/.venv/bin/python scripts/adaptive_watch/railway_cv.py /private/manifest.json --zone /private/zone.json --out /private/cv.json
~/hafnia-hackathon-2026/.venv/bin/python scripts/adaptive_watch/inspect_cv.py /private/cv.json /private/recording-directory
~/hafnia-hackathon-2026/.venv/bin/python -m unittest discover -s tests
```

All ML execution stays on Linux. No frontend, services, network settings, accounts,
new alarm definitions, or default XProtect rules were changed.
