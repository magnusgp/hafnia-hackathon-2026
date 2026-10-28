# Adaptive Watch — Checkpoint A: ML feasibility

Date: 2026-10-21. Branch `feat/adaptive-watch`. Protocol: [preregistration.md](preregistration.md) (committed before any score was computed). Raw numbers: `results/{ped2,avenue}/{val,test}.json`.

## Verdict

**The pre-registered gate FAILS.** On the Avenue final test, the primary DINOv2 model retained 14/20 events at a 30 % window budget (0.70). Both the 0.80 target and equal-budget periodic selection (0.80) beat it.

Recommendation: **do not proceed to Checkpoint B on this evidence.** A post-hoc analysis suggests a narrower hypothesis that is worth one confirmatory test on fresh data before spending Hafnia requests (see Next step).

## Setup (as registered)

- **Model.** Frozen `facebook/dinov2-small` (rev `ed25f3a3`, Apache-2.0). Last-layer patch tokens at 224 px height.
  - Camera-specific memory: patch novelty = 1 − max cosine similarity to normal-footage patches from the same or an adjacent grid cell.
  - Frame score = max patch novelty, then causal smoothing. Nothing is trained.
- **Baselines.**
  - Frame-difference motion (p99 of the absolute difference).
  - DINOv2+motion z-score fusion.
  - Periodic and random selection at equal budget.
- **Data.**
  - UCSD Ped2: MD5 verified against the published value.
  - CUHK Avenue: SHA-256 recorded on first download, since none is published.
  - Neither dataset publishes a licence. Both are used for research benchmarking only; data and frames stay outside Git.
- **Splits.** At the original-clip level, fixed by index.
  - Ped2: memory Train001–012; calibration Train013–014; validation Test001–004; final test Test005–012 plus normal Train015–016.
  - Avenue: memory train01–14; calibration train15; validation test01–07; final test test08–21 plus normal train16.
- **Units.** Windows ≈ 2 s. Events are anomalous runs, merged across gaps shorter than one window. Budget = top-k windows pooled over the phase, with no per-video normalisation.
- **Configuration.** Chosen on validation window AUPRC and committed before each final test (`results/*/config.json`). Each final test ran once.

## Results — final test (evaluated once)

### CUHK Avenue (gate dataset): 14 clips + 1 normal clip, 20 events, 169 windows, 27 % anomalous frames

| method | frame AUROC (annotated clips) | window AUROC | window AUPRC | events @5 % | @10 % | @20 % | @30 % | @50 % |
|---|---|---|---|---|---|---|---|---|
| **DINOv2 (primary)** | 0.776 | 0.862 | 0.810 | 7/20 | 10/20 | 13/20 | **14/20** | 18/20 |
| motion | 0.689 | 0.740 | 0.610 | 5 | 9 | 13 | 16 | 20 |
| fused | 0.792 | 0.861 | 0.826 | 8 | 11 | 14 | 16 | 19 |
| periodic (mean over phases) | – | – | – | 3.3 | 6.7 | 11.8 | 16.0* | 18.5 |
| random (mean of 1000) | – | – | – | 3.3 | 5.7 | 9.8 | 12.5 | 16.3 |

\* At a nominal 30 % budget, periodic selects every 3rd window, which is 33 % of the footage. This favours the baseline.

Precision of the selected windows (fraction that contain anomalous frames), DINOv2: 1.00 at 5 % and 10 % budgets, 0.88 at 20 %, 0.73 at 30 %. The anomalous-window base rate is 0.40.

Operating point (threshold = highest window score on calibration-normal footage):

| method | selected | event recall | false windows / normal windows | false alerts per hour of normal footage |
|---|---|---|---|---|
| DINOv2 | 37 % | 0.80 | 17 / 102 | 308 |
| motion | 11 % | 0.50 | 5 / 102 | 90 |
| fused | 23 % | 0.75 | 5 / 102 | 90 |

The normal footage behind these rates totals only about 3.4 minutes, so they are very uncertain. Either way, novelty alone would be an unacceptable alarm source, which confirms the design rule that local novelty must never raise a security alarm by itself.

### UCSD Ped2 (detector validity only): 8 clips + 2 normal clips, 8 events, 87 % anomalous frames

| method | frame AUROC (annotated clips) | frame AUROC (incl. normal clips) | events @30 % | periodic @30 % |
|---|---|---|---|---|
| DINOv2 | 0.780 | 0.871 | 6/8 | 8/8 |
| motion | 0.647 | 0.871 | 5/8 | 8/8 |
| fused | 0.834 | 0.939 | 5/8 | 8/8 |

As registered, budget metrics on Ped2 are non-discriminative: every event spans at least 5 windows. These numbers cover 8 of the 12 standard test clips, so they are **not comparable** with published full-protocol Ped2 numbers.

### Validation to test generalisation

DINOv2 annotated-clip frame AUROC went from 0.986 to 0.780 on Ped2, and from 0.713 to 0.776 on Avenue. With 4–7 validation clips, the validation estimates were not reliable predictors.

## Failure analysis (post-hoc, does not change any registered result)

- **Novelty is not the same as the annotated anomaly.**
  - Avenue test09: the highest-scoring false positives show a staged actor standing unusually close to the camera, in frames labelled normal. Only her actions (throwing, waving) are annotated.
  - Ped2 Test006: an ordinary pedestrian in distinctive clothing outranks the annotated cyclist. Within-clip AUROC is 0.16.
  - In both cases the model is doing what it was built for: flagging rare appearance. That is exactly the gap a semantic qualifier such as Hafnia is meant to close. This is a hypothesis, not a measured result.
- **Motion-defined anomalies are invisible to a per-frame appearance memory.**
  - Ped2 Test012: the anomaly inside a dense crowd scores at normal-footage level (within-clip AUROC 0.50).
  - Avenue misses include long events where the actor is already in view, such as test17 and test18 (whole clip), and short object events (test13, test21).
- **Pooled top-k concentrates the budget.** Salient events absorb many windows. At 30 %, 18 of the 33 selected Ped2 windows came from two clips. This is why model recall falls behind periodic at larger budgets, even though window-level ranking (AUROC 0.86) is well above chance.

### Clip-level bootstrap (post-hoc, 2000 resamples of the 14 Avenue test clips)

Event-recall difference vs periodic at equal budget:

| budget | DINOv2 | fused |
|---|---|---|
| 5 % | +0.18 [+0.04, +0.36] | +0.23 [+0.08, +0.40] |
| 10 % | +0.17 [−0.03, +0.39] | +0.27 [+0.06, +0.48] |
| 20 % | +0.01 [−0.19, +0.24] | +0.13 [−0.10, +0.35] |
| 30 % | −0.07 [−0.27, +0.16] | −0.00 [−0.19, +0.18] |

These are twelve unplanned comparisons on a test set that has now been seen. Treat them as hypothesis-generating only (`scripts/adaptive_watch/bootstrap.py`, `results/avenue/bootstrap_posthoc.json`).

## Budget realism (arithmetic, not a measurement)

- 500 completed Hafnia requests/day against one continuously recorded camera means:
  - 2 s windows: 500 / 43 200 = 1.2 % of windows.
  - 15 s clips: 500 / 5 760 = 8.7 % of clips.
- The operationally relevant regime is therefore ≤ 10 %, not 30 %. In hindsight, the provisional 30 % gate was looser than the deployment constraint.
- This is stated to inform the next pre-registration. It does **not** retroactively change the gate.

## Hardware

| | M1 Pro, MPS (this session) | T4 VM |
|---|---|---|
| DINOv2-S, 640×360 → 224×392, batch 16 | 14.9 ms/frame (probe); 20–29 ms/frame in Avenue extraction | **not measured** |
| Novelty scoring, 1 340-frame memory | 50 ms/frame | **not measured** |
| Frame decode (PyAV / TIFF) | 1.3–1.8 ms/frame | not measured |

At about 65 ms/frame on MPS, one device processes about 15 frames/s, i.e. roughly 3 cameras at 5 fps. Novelty scoring, not DINOv2, dominates; it scales with memory size, and a coreset or approximate nearest-neighbour index would cut it.

**Blocker:** this session cannot reach the Windows VM, so `nvidia-smi`, VRAM, CUDA/driver compatibility and T4 latency are unverified. Run on the VM:

```powershell
git fetch; git checkout feat/adaptive-watch
uv sync --group ml
nvidia-smi
uv run --group ml python aw.py probe --save   # writes results/hardware/probe-cuda.json
```

## XProtect recorded-video access (desk research, unverified on the VM)

Read-only options, in order of what to try first:

1. **MilestonePSTools, already installed.**
   - `Get-Snapshot -Camera … -Timestamp … -EndTime … -Interval 0.5 -Save -Path …` returns JPEGs from recordings, transcoded on the Recording Server.
   - `Start-Export -Format MKV -StartTime … -EndTime …` exports without transcoding, and Python decodes it with PyAV. This is the lower server load option.
2. **MIP SDK component.** `RawVideoSource` / `JPEGVideoSource` / `MKVExporter` (.NET) is the scalable route. Alternatively, the documented ImageServer protocol (TCP 7563, `goto` / `next`).
3. **Not recommended.**
   - REST `JpegGet` on a recorded timestamp is reported only on Milestone forums (2025 R3+) and is undocumented.
   - WebRTC playback (GA 2024 R1) has no Python sample.

None of these has been executed on p022. The Hafnia gateway's own export path is not evidence that any of them works.

## Failed assumptions

1. Ped2 could test the VLM-budget question. Wrong: its events are too long. This was identified before scoring and registered.
2. Frozen appearance features would carry the novelty signal. Partly wrong: motion-defined and action-defined anomalies are missed, and normal-but-rare appearance dominates false positives.
3. Validation on 4–7 clips would predict test behaviour. Wrong on Ped2: AUROC fell from 0.986 to 0.780.
4. A 30 % budget is the right operating regime. Hindsight says ≤ 10 % (see budget realism).

## Next step (proposal, needs your decision)

Run **one confirmatory, pre-registered test on independent multi-camera data**: ShanghaiTech Campus, 13 cameras, which is directly "camera-specific".

- Fused appearance+motion as primary.
- Gate at a ≤ 10 % budget vs periodic.
- Per-camera memories.
- No re-use of Avenue or Ped2 for selection.

Download access, licence and size for ShanghaiTech are not yet verified. If that confirmatory test passes, proceed to Checkpoint B with up to 10 approved Hafnia requests on selected and non-selected windows. If it fails, stop the local-novelty line; at most consider a narrow, trainable task with independent labelled data.

## Reproduce

```bash
uv sync --group ml
uv run --group ml python -m unittest discover -s tests
uv run --group ml python aw.py fetch ped2 && uv run --group ml python aw.py fetch avenue
uv run --group ml python aw.py extract ped2 && uv run --group ml python aw.py extract avenue
uv run --group ml python aw.py evaluate ped2 --phase val     # rewrites config.json; commit before test
uv run --group ml python aw.py evaluate ped2 --phase test --rerun
uv run --group ml python scripts/adaptive_watch/bootstrap.py avenue
```

Data and weights are cached in `~/.cache/adaptive-watch` and `~/.cache/huggingface`, outside Git. Override them with `AW_DATA` / `AW_CACHE`. Contact sheets of examples are written to `runs/adaptive-watch/` (git-ignored, dataset imagery).
