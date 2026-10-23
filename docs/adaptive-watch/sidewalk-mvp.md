# Sidewalk hybrid MVP — 23 October 2026

Select **persistent sidewalk object review**, with e-scooter as the flagship and
bin as the second technical example. Localization supplies useful spatial and
temporal evidence on both saved scenes; vehicle-queue fallback is unnecessary.
This is a working retrospective review slice, not validated automatic obstruction
detection. No additional Hafnia inference, event dispatch or XProtect configuration
change was performed. Existing infrastructure demonstrations were not repeated.

## Semantic adjudication

Both exact railway prompts ask whether a person descends onto the track area **or
remains there**, distinguishing platform occupancy. Both responses deny descent.
The saved timestamped frames show clear standing track-bed entry bracketed by
11:03:48.013–48.513 UTC and subsequent crossing, inside the assessed
11:03:39–11:03:52 interval on 22 October. Inspection of the original saved MKV
at PTS 8–13 seconds confirms the action sequence. MKV PTS alone does not establish
absolute UTC; that bracket comes from server-timestamped JPEGs. This is a missed
visible action, not an omitted crucial recording interval or a stronger prompt.
Earlier seated-edge contact remains ambiguous: neither the old polygon crossing
nor inferred feet establishes physical track occupancy. No intent is established.

Both gate prompts ask about manipulation with a tool and explicitly exclude any
assumption of successful entry or criminal intent. Both responses describe tool
manipulation but return `not_observed` because the gate stays closed. Saved
frames in the exact 11:04:39–11:04:52 interval show a person crouching and working
with an implement at the gate/chain area, then leaving. Detailed lock contact is
partially occluded in the dark; no opening, entry, damage or criminal intent is
established. No original gate MKV is saved, so review is limited to timestamped
snapshots. This is principally an outcome/evidence contradiction and an added
success requirement, with local visual ambiguity about the mechanism. It is not
proof of a break-in. Original negative outcomes remain unchanged.

Private `semantic-adjudication.json` retains exact prompts, original responses,
summary IDs, source hashes and timestamped frame identities for all four cases.
The busy-street controls are separate requests, not railway/gate incident footage.

## Common CV pipeline and measured contribution

Linux A10G executed `scripts/adaptive_watch/sidewalk_cv.py` with Transformers
4.46.3, PyTorch 2.5.1+cu124 and pretrained **google/owlvit-base-patch32** at resolved
revision `cbc355fb364588351c5d51c7f74465e8e7ec6f72`. Safetensors SHA-256:
`4dbe0399f0b7d7c8dddf1535a98769cc30743bebc877aea681998c8d984ce52b`.
OWL-ViT accepts text queries for open-vocabulary localization; suitability here
was assessed by inspecting the resulting boxes, not assumed from COCO classes.
Reference: [Google model card](https://huggingface.co/google/owlvit-base-patch32).

Queries: “a green wheelie bin”, “a fallen trash bin”; “an electric scooter”,
“a scooter lying on the ground”. Score cutoff 0.10, class-agnostic NMS IoU 0.5.
All boxes are retained in private outputs. Tiny distant false detections are
visible; the temporal measurement uses the largest target box with image area
at least 1%. This is a foreground association hypothesis, not a general tracker.
Rider and scooter are sometimes enclosed together before dismounting.

The draft walkway polygon is `[[0,.44],[.18,.43],[.68,1],[0,1]]` in normalized
image coordinates. **Operator approval is outstanding.** Overlap is box/polygon
area, not a segmentation mask or ground footprint. Image geometry cannot prove
accessible clearance. The scooter failed an initial 50% overlap gate; the review
gate was changed to 10% to admit partial overlap explicitly. This is disclosed
same-clip calibration, not a validated threshold or a model improvement claim.

Stationarity requires consecutive samples no more than 1.5 seconds apart, with
center drift at most .025 normalized image units from a run's anchor. Review
candidates additionally require a 3-second sampled span and .05 displacement
from the first overlapping foreground center. This prevents the initially static
bin from becoming a new-onset candidate, but misses already-present obstructions.

| Evidence on 22 October, UTC | Bin | E-scooter |
| --- | --- | --- |
| Exact Hafnia/CV interval | 11:04:31–11:04:43 | 11:04:48–11:05:01 |
| Timestamped samples in interval | 12 at 1 Hz | 13 at 1 Hz |
| Bounded stationary run | 11:04:39.593–42.593 | 11:04:55.009–11:05:00.009 |
| Sampled stationary span | 3.0 s / 4 samples | 5.0 s / 6 samples |
| Maximum anchor-center drift | .00379 | .00690 |
| Minimum box/walkway overlap in run | 77.9% | 43.0% |
| First visibly departing-actor sample | 11:04:40.593 | 11:04:56.009 |
| Sampled span after actor departs | **2.0 s** | **4.0 s** |

Manual onset brackets are 38.593–39.593 for the bin and 54.009–55.009 for the
scooter within their respective minutes. These are stationarity onset brackets,
not verified walkway-entry times. Physical entry/exit is not established; the
objects remain visible at the final measured sample. Later disappearance occurs
at synthetic loop reset and must not be interpreted as physical removal.

Hafnia supports leaving objects in both prompt variants, but its approximate
timings do not provide an auditable location-specific duration. Local CV adds
timestamped boxes, center trajectories, bounded stationarity and explicit spatial
overlap. It does **not** establish full obstruction, intent, long-term abandonment,
or better incident accuracy. There is no supervised training or independent
labeled test set. Repeated synthetic loops count as the same scene.

## Simple change baselines

Both baselines use grayscale differences >25/255 within the same polygon:
successive-frame motion, and change from the first selected frame. The latter is
a basic background-change proxy; its reference contains objects and is not a clean
background model. A fixed >1% changed-pixel rule produces:

| Scene / sampled phase | Motion positives | Reference-change positives |
| --- | --- | --- |
| Bin before stable candidate | 7/7 comparisons | 7/8 frames |
| Bin stable candidate | 4/4 comparisons | 4/4 frames |
| Scooter before stable candidate | 5/6 comparisons | 5/7 frames |
| Scooter stable candidate | 6/6 comparisons | 6/6 frames |

Motion ranges overlap: bin 4.05–28.01% before vs 3.42–40.21% during;
scooter .80–5.22% before vs 2.70–4.39% during. The baselines signal change but
cannot attribute it to a stationary object at a particular position. Reference
change rises after placement but also fires before it. These are technical
comparisons on the same cycle, not labeled accuracy or superiority estimates.
The bin's initial 5-second static run is explicitly excluded by displacement;
no pre-placement run qualifies in the scooter interval.

## Private evidence and integration proposal

Ignored `runs/hybrid/sidewalk-v2/` contains detector JSON, timestamped JPG overlays,
`bin-joined.json`, `scooter-joined.json`, model hashes, semantic adjudication and
manual review. Original videos, raw responses and private overlays remain outside
public Git. Sidewalk sources are saved server-timestamped JPEG sequences; no
sidewalk MKV exists, so no video-file hash is invented. Each selected JPEG and
the original acquisition manifest are SHA-256 verified.

`join_sidewalk.py` verifies exact camera and UTC assessment interval, original
manifest identity and selected frame hashes. It preserves submitted prompts,
original responses, summary IDs, original parse results and repair provenance.
The gateway's added default `AiModelId=traffic-general` is retained explicitly;
submitted request fields must match exactly and other enrichments are rejected.
Every joined response is retrospective only; normalized/repaired JSON cannot
satisfy automatic-dispatch eligibility. Both decisions are
`review_recording_and_approve_walkway` and `automatic_dispatch_eligible=false`.

`prepare_sidewalk_event.py` prepares bytes only for the distinct proposed event
**Adaptive Watch Sidewalk Obstruction**. The exact GUID/name source mapping is
verified against `cameras.local.json` and saved privately in
`native-proposal/proposal.json`; exact XML and SHA-256 are alongside it. There is
no new definition, alarm or event send. Native definition IDs remain unassigned.

Operator workflow: review exact recorded interval and overlays, confirm usable
walkway overlap, then explicitly approve a distinct Analytics Event and alarm
definition scoped to the verified scooter camera. Separate human approval of the
exact XML digest is required before any send. Preserve the existing SQLite
claim-before-POST ledger, duplicate suppression and uncertain-result reconciliation.
The proposed episode key is shared across prompt variants for the same camera
and interval. Future live operation also needs explicit episode handling across
overlapping recording windows; this retrospective slice does not implement it.
An empty HTTP 200 remains transport acceptance; verify the actual native alarm.

## Reproduction and status

On Linux, use the existing ML environment and a private configuration with pinned
model revision, exact intervals, manifest paths, queries and walkway polygon:

```text
python scripts/adaptive_watch/sidewalk_cv.py PRIVATE_CONFIG --out PRIVATE_OUTPUT
```

On Windows, join each detector output with its original saved evaluation directory
and acquisition manifest using `join_sidewalk.py --evaluations ... --manifest ...
--model-audit ... --out ...`. Then prepare the offline proposal with
`prepare_sidewalk_event.py JOINED --camera-map cameras.local.json --out PRIVATE_DIR`.
These scripts have no Hafnia submission or native dispatch capability.

Existing unrelated working-tree edits were preserved, with an additional private
patch/copy checkpoint under `runs/hybrid/`. Initial live remote verification
confirmed `23398a7`; local recovered-response commit `c40c1b7` is preserved.
Final test and publication results are recorded in the delivery message.
