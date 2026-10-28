# Visibility degradation (fog / haze) — pre-registration

Date: 2026-10-21. Branch `feat/adaptive-watch`. This document is committed **before any feature, score or model output was computed** on the data below. Seen beforehand: the dataset licences, the annotation format and per-split **label counts** (no images inspected for selection, no scores).

## Why this task (selection from three candidate families)

| criterion | 1. interaction / temporal | 2. physical state / change | **3. visibility** |
|---|---|---|---|
| independent labelled data | MEVA is the only open licence (CC BY 4.0), 516 GB, one site, scripted actors; others research-only or request-only | none with damaged/intact labels from fixed cameras; change sets research-only or unlicensed, mostly moving cameras | **Transient Attributes**: CC BY 4.0, 1.8 GB, 101 fixed webcams, real crowd-sourced fog labels, official camera-disjoint split. **Digitraffic**: CC BY 4.0, 236 fixed road cameras within 200 m of an instrumented visibility sensor |
| relevance to a provided XProtect camera | weak (no camera with this scene confirmed) | `vandalism` camera, but no data | `highway_traffic_overcast_weather` and the existing `roadway-visibility` contract |
| trivial baseline already solves it? | **yes** for stopped vehicle / zone entry (AI City 2021 winner ≈0.94 with stationarity rules) | open | **unknown → measured here** (dark channel, contrast, sharpness) |
| T4 feasibility | heavy (tracking, long video) | moderate | trivial (frozen features + logistic regression) |
| customer value | duplicated by rule engines | high but untestable | measurable: hours a camera's view is degraded, false alerts per camera-day |

Decision: **family 3, narrowed to fog/haze visibility degradation.** Night, precipitation and glare are reported as secondary attributes only.

**Camera-local vs weather discrimination is out of scope.** No public dataset has real, labelled camera-local faults on fixed CCTV. UHCTD's are synthetic, and arXiv 2607.14760 says so explicitly. Staging faults on the hackathon cameras is excluded.

## Data and splits (all at camera level)

- **Transient Attributes (TA)**, `imageAlignedLD`, SHA-256 `2848439a…2e62` (aligned_images.tar), annotations `d80ceb2c…ee8a55`, splits `c757bbe5…62f9`.
  - Official `holdout_split`: 81 training cameras / 20 test cameras, no overlap.
  - Validation: the training cameras are sorted by ID and every 5th is taken (index % 5 == 0). That gives 17 validation cameras and 64 fit cameras.
- **Labels (TA).** The fog attribute score is in [0, 1].
  - Positive: score ≥ 0.6.
  - Negative: score ≤ 0.3.
  - Excluded from training and metrics: scores in between. Their count is reported.
- **External test (Digitraffic)**, `adaptive_watch/digitraffic.py`, collected forward from 2026-10-21.
  - Camera set: frozen on first run (`cameras.json`).
  - Label: the co-located sensor's `NÄKYVYYS_M` at most 10 min from the capture time.
  - Positive: < 1000 m. Negative: ≥ 5000 m. Readings in between are not labelled.
  - The label comes from an instrument, independent of any image annotation.

## Methods

Every method outputs one score per image, where higher means more fog/haze.

Fixed baselines (no learning; the direction is fixed a priori):
- **B1** Dark-channel prior: mean dark channel, 15 px patch, on an image resized to 360 px height.
- **B2** Negative RMS contrast of luminance.
- **B3** Negative log Laplacian variance (sharpness).
- **B4** Logistic regression on [B1, B2, B3, mean luminance, mean saturation]. This is the simple-CV supervised baseline.

Pretrained-only baseline:
- **P1** Zero-shot CLIP ViT-B/32 (`openai/clip-vit-base-patch32`, rev `3d74acf9`). The score is the softmax probability of "a photo of a foggy scene with low visibility" against "a photo of a clear scene with good visibility".
- Its model card puts deployed use out of scope, so it is a baseline only.

Learned candidates. Frozen `facebook/dinov2-small` (rev `ed25f3a3`, Apache-2.0) features: the CLS token concatenated with the mean patch token, then standardised, then logistic regression.
- **M1** Features as is.
- **M2** Per-camera centering: subtract the camera's mean feature over all of its images in the same split. This uses no labels; in deployment it would be the camera's own unlabelled history.
- Grid: C ∈ {0.01, 0.1, 1, 10}, class-balanced weights.

## Selection, metrics, stopping rule

1. **Selection.** Each candidate is fitted on the 64 fit cameras and scored on the 17 validation cameras. The learned model is the one with the highest pooled validation AUPRC among M1/M2 × C. The comparison baseline is the one with the highest validation AUPRC among B1–B4 and P1. The decision threshold is the max-F1 threshold on validation. All of this is written to `results/visibility/config.json` and **committed before the test**.
2. **Final TA test.** It runs once, with the frozen config; there is no refit. This is enforced in code, as for Checkpoint A.
3. **Primary metric.** Image-level AUPRC on the 20 TA test cameras.
4. **Gate.** Selected model AUPRC − baseline AUPRC ≥ +0.05, **and** the lower bound of the 95 % camera-level bootstrap CI of that difference (2000 resamples of cameras) is > 0.
5. **Secondary metrics.**
   - AUROC.
   - Precision, recall and F1 at the frozen threshold.
   - Per-camera AP distribution.
   - Secondary attributes (night, rain, snow) reported only as ranking of their own scores. No new models are trained for them.
   - Latency: ms/image and VRAM.
   - Failure cases: the highest-scoring false positives and lowest-scoring false negatives, by file name only.
6. **External test.** It runs once with the frozen TA model and threshold, at the earlier of:
   - ≥ 50 positive images from ≥ 8 distinct cameras; or
   - 2026-10-29 12:00 CET.

   If fewer than 20 positives from fewer than 5 cameras exist at that time, the result is "insufficient external data" and no claim is made.

   Metrics:
   - AUROC, AP, and precision, recall and F1 at the frozen threshold.
   - False alerts per camera-day, computed as negative-image FPR × 144 images/day at the 10-min cadence.
   - Daylight and night split by solar elevation.
   - Camera-level bootstrap CIs.

   External gate: AUROC ≥ 0.80 **and** above the selected baseline's AUROC.

If the gate fails, the trained component is not justified, and the hybrid system uses the better baseline or nothing. This is reported as such.

## Role in the hybrid system (not tested in this sprint)

1. The local model scores every sampled frame at negligible cost.
2. Sustained degradation, k consecutive frames above the threshold, triggers at most one Hafnia `roadway-visibility` assessment. That assessment establishes visible evidence for whether lanes and vehicles remain distinguishable.
3. Only validated positive evidence becomes a native analytics event (`scene_contracts/analytics_event.py`).
4. Hafnia is not used for every frame, and not as the label source.

## Known limitations, stated in advance

- TA images are 2010–2013 low-resolution webcams, not traffic CCTV. Fog labels are crowd judgements.
- Digitraffic stills come every 10 min, so consecutive images of one fog event are correlated. This is handled by camera-level bootstrap, not by image-level significance.
- The "nearest" sensor is ≤ 200 m away, not guaranteed to be in the field of view.
- Per-camera centering (M2) uses the test split's unlabelled images. Its means shift with the fog prevalence of each camera's collected set; on Digitraffic, the negatives are subsampled.
