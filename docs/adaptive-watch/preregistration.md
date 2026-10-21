# Adaptive Watch — pre-registered evaluation (Checkpoint A)

Committed on 2026-10-21 **before any novelty score was computed** on any annotated clip. The Git history of this file and of `results/<dataset>/config.json` is the audit trail. Any later deviation is recorded at the end of this file and in the report, never edited in place.

Known before registration: dataset READMEs, annotation files and their label statistics (below). No model or baseline output had been produced.

## Question

Can a camera-specific visual novelty model choose a small fraction of footage windows for Hafnia VLM qualification while retaining most annotated anomalous events, better than spending the same request budget on periodic sampling?

The model scores **visual novelty relative to one camera's normal footage**. It does not detect intent, danger or crime.

## Datasets and integrity

| | UCSD Ped2 | CUHK Avenue |
|---|---|---|
| Source | svcl.ucsd.edu `UCSD_Anomaly_Dataset.tar.gz` | cse.cuhk.edu.hk `Avenue_Dataset.zip`, `ground_truth_demo.zip` |
| Integrity | MD5 `5006421b89885f45a6f93b041145f2eb` (published, verified) | SHA-256 recorded on first download (no published checksum) |
| Terms | No licence text published. README requests citation of Mahadevan et al., CVPR 2010 | No licence text published. Page cites Lu, Shi, Jia, ICCV 2013 |
| Use here | Research benchmarking only; never redistributed; raw data and frames stay outside Git | same |
| Frames | 360×240 grey, all frames, rate undocumented (10 fps assumed for per-hour figures) | 640×360 colour, 25 fps, every 5th frame scored (5 fps) |
| Labels | `gt_frame` ranges in `UCSDped2.m` | frame anomalous iff its `volLabel` mask has any positive pixel |

## Splits (original-sequence level, fixed by index, not by content)

| role | Ped2 | Avenue |
|---|---|---|
| memory (normal, fitted) | Train001–012 | train01–14 |
| validation normal (calibration) | Train013–014 | train15 |
| validation annotated (configuration choice) | Test001–004 | test01–07 |
| final-test normal (alarm load) | Train015–016 | train16 |
| final test annotated (evaluated once) | Test005–012 | test08–21 |

Label statistics of the annotated splits:

| | events (merged) | event length, frames (min / median / max) | anomalous frames |
|---|---|---|---|
| Ped2 validation | 4 | 86 / 133 / 150 | 72.8 % of 690 |
| Ped2 final test | 8 | 93 / 142 / 180 | 86.8 % of 1320 |
| Avenue validation | 16 | 2 / 9 / 64 | 20.7 % of 1486 |
| Avenue final test | 20 | 3 / 19 / 86 | 27.3 % of 1589 |

**Consequence registered in advance:** in Ped2 every event spans at least 5 windows, so equal-budget periodic selection at 30 % retains every event by construction. The 80 %/30 % gate cannot discriminate on Ped2. Ped2 therefore checks detector validity (frame AUROC) only. **The feasibility gate is decided on Avenue.**

## Units

- Window: non-overlapping, ≈2 s — 16 frames (Ped2), 10 sampled frames (Avenue). Window score = maximum frame score. A window is anomalous if any of its frames is.
- Event: maximal run of anomalous frames; runs separated by fewer than one window of normal frames are merged. An event is retained if any selected window overlaps it.
- Budget: the top ⌈b·N⌉ windows by score, pooled over all clips of the phase (annotated plus held-out normal), b ∈ {5, 10, 20, 30, 50} %. No per-video normalisation.

## Methods

1. **DINOv2 (primary).** Frozen `facebook/dinov2-small` @ `ed25f3a3`, last-layer patch tokens at 224 px height (aspect preserved), L2-normalised. Memory = every 2nd frame of the memory clips. Patch novelty = 1 − max cosine similarity to memory patches in the same or an adjacent (3×3) grid cell. Frame score = patch aggregation, then causal moving average.
2. **Motion baseline.** Absolute grey-level difference to the previous scored frame; frame score = mean or 99th percentile, then causal moving average.
3. **Fused (secondary).** Sum of DINOv2 and motion frame scores, each z-scored with statistics from validation-normal clips.
4. **Periodic baseline.** Every round(1/b)-th window of each clip, averaged over all phases. Its actual selected fraction is reported (33 % at b = 30 %, which favours the baseline).
5. **Random baseline.** Uniform choice of ⌈b·N⌉ windows, mean of 1000 draws.

Configuration grid, chosen **on validation only** by pooled window-level AUPRC:
DINOv2 aggregation ∈ {max, mean of top 1 % patches} × smoothing ∈ {1, 3, 5} frames; motion statistic ∈ {mean, p99} × smoothing ∈ {1, 3, 5}. Fixed, not tuned: model, layer, resolution, 3×3 neighbourhood, memory stride, window length, k = 1.

Operating threshold for each method = maximum window score on validation-normal clips (zero false alerts on calibration footage), frozen with the configuration.

## Primary outcome and gate

On **Avenue final test** (test08–21 + train16), DINOv2 at a 30 % window budget:

- **PASS** if event recall ≥ 0.80 (≥ 16 of 20 events) **and** exceeds the periodic baseline's mean event recall at the same nominal budget.
- **FAIL** otherwise. A failure is reported as such; the final test is not re-run with changed settings.

## Secondary outcomes (reported, not gating)

Frame and window AUROC/AUPRC (all clips, and annotated clips only); event recall, window precision, anomalous-window recall and median detection delay at every budget; operating-point selected fraction, event recall and false alerts per hour of normal footage; the same for motion and fused; Ped2 frame AUROC on Test005–012 (not comparable to the literature's all-12-clip protocol); decode, DINOv2 and novelty latency per frame on the measuring device; representative highest-scoring true/false positive windows and lowest-scoring anomalous windows.

No VLM accuracy is reported: no Hafnia request is part of Checkpoint A.

## Procedure

1. `aw.py extract` for all clips (features only, no labels touched).
2. `aw.py evaluate <ds> --phase val` writes `results/<ds>/config.json` and `val.json`.
3. Commit the config. `--phase test` refuses to run on an uncommitted or modified config and refuses a second run without `--rerun`.
4. `aw.py evaluate <ds> --phase test` once per dataset.

## Deviations

None yet.
