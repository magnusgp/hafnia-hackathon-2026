# Visibility degradation (fog / haze) — Transient Attributes final test

Date: 2026-10-21. Protocol: [preregistration.md](preregistration.md), committed in `085fb0e` before any score existed. Frozen config: `results/visibility/config.json`, committed in `223c2f1` before the test. Raw results: `results/visibility/{val,test}.json`. The test ran once.

## Verdict

**The pre-registered gate FAILS.**
- The trained DINOv2 head beats the best baseline (zero-shot CLIP, chosen on validation) by **+0.045 AUPRC**. The gate required ≥ +0.05.
- The camera-level 95 % CI of the difference is **[−0.041, +0.127]**, so it includes 0.
- In absolute terms the model ranks fog well on unseen cameras, but it has **not been shown to be better than a pretrained-only model**.

## Test: 20 unseen cameras, 1 465 labelled images, 236 fog, 202 ambiguous excluded

| method | AUROC | AUPRC | precision | recall | F1 | FPR |
|---|---|---|---|---|---|---|
| **M1 DINOv2-S + logistic regression (selected)** | **0.963** | **0.878** | 0.81 | 0.83 | **0.82** | 0.037 |
| P1 zero-shot CLIP (selected baseline) | 0.951 | 0.832 | 0.80 | 0.72 | 0.76 | 0.034 |
| B4 handcrafted + logistic regression | 0.815 | 0.577 | | | | |
| B3 sharpness (neg. log Laplacian var.) | 0.695 | 0.387 | | | | |
| B1 dark-channel prior | 0.650 | 0.287 | | | | |
| B2 low contrast | 0.617 | 0.241 | | | | |
| *M2 DINOv2 + per-camera centering (not selected)* | *0.970* | *0.906* | | | | |

Thresholds were frozen at the validation max-F1 point. M2 lost on validation by 0.015 AUPRC. Its higher test score is **post hoc** and cannot be claimed.

- **Per-camera AP (learned).** All 20 test cameras contain fog. AP ranges from 0.79 to 1.00 with a median of about 0.95. The weakest cameras are 00017660 (0.79), 90000003 (0.85) and 00008915 (0.86).
- **Fog-score false-positive rate on clear images with other conditions** (labelled ≥ 0.6, at the frozen threshold):
  - night: 5.3 % of 207
  - snow: 10 % of 140
  - rain: 12.5 % of 8

## What this does and does not establish

- **Classic haze cues are not a usable fog detector across cameras.** Dark channel, contrast and sharpness reach AUPRC 0.24–0.39, and 0.58 combined. Pretrained features clearly beat them.
- **Training a head on frozen DINOv2 is not proven better than zero-shot CLIP.**
  - The point estimate favours the head: F1 0.82 vs 0.76 at the frozen thresholds.
  - The bootstrap over cameras cannot exclude no difference.
- **For deployment, the licence matters.**
  - OpenAI's CLIP model card puts deployed use out of scope.
  - DINOv2 is Apache-2.0.
  - So the trained head is the deployable option of the two. That is a licensing argument, not a measured performance advantage.
- **Failure cases:**
  - Snow-covered scenes give the top false positives: whitish, low-contrast and haze-like, e.g. camera 00008915.
  - Night scenes give false positives too, e.g. 90000003.
  - The lowest-scoring fog images are borderline labels (fog score 0.61) at night or in snow. Crowd labels near the cut-off are noisy.
- **Scope limits:**
  - TA images are 2010–2013 low-resolution webcams, not highway CCTV, so this does not transfer to the XProtect camera by itself.
  - The external Digitraffic test is the relevant check: real highway cameras with instrument labels.

## Latency (M1 Pro, MPS; T4 not measured)

| stage | ms/image |
|---|---|
| JPEG decode | 7.9 |
| handcrafted cues (360 px) | 11.9 |
| DINOv2-S embedding (one image per pass, unbatched) | 23.1 |
| CLIP zero-shot (batch 32) | 8.7 |
| logistic regression | < 0.1 |

At 1 sampled frame per 10 s per camera, the learned path costs about 31 ms/frame on the M1 Pro, i.e. hundreds of cameras per device. Cost is not the constraint for this task.

## Next (pre-registered, no tuning)

External test: `uv run --group ml python vis.py external`. It runs once, with the frozen model and threshold, when the collector reaches 50 fog images from 8 cameras, or on 2026-10-29 12:00 CET. Its gate is AUROC ≥ 0.80 and above zero-shot CLIP.

Nothing in this document changes after the external result.
