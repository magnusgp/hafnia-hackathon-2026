# ML recovery sprint — handoff (2026-10-21)

Branch `feat/adaptive-watch`; the commit is given in the git log entry that adds this file. Nothing is merged to `main`. No Hafnia requests, no UI, no XProtect, auth, firewall or Tailscale changes, and no event sent.

**Nothing in this document was run on p022.** This session cannot reach the VM. Every hardware or XProtect number below is from the M1 Pro (MPS), or is a command still to run.

## 1. T4 and XProtect

| item | status |
|---|---|
| T4 visibility, VRAM, CUDA (not CPU fallback) | **not measured**. `aw.py probe --require-cuda --save` exits non-zero on fallback |
| DINOv2 + novelty latency | MPS: 16 ms/frame at 640×360, 22 ms at 1080p; novelty 46 ms (1 340-frame memory). T4: not measured |
| recorded-frame acquisition | `scripts/acquire_recording.ps1` written, **never executed**. No PowerShell was available here, so not even its syntax is checked |
| video→tensor path | `aw.py footage` tested locally on synthetic JPEG/manifest and MKV inputs, including exact timestamps and fixed-grid sampling |

### VM runbook (Windows PowerShell, repo root)

```powershell
git fetch origin
git switch feat/adaptive-watch
git pull
uv sync --group ml
nvidia-smi
uv run --group ml python aw.py probe --require-cuda --save
```

Expected:
- `"device": "cuda"`, `"gpu": "Tesla T4"`, `vram_gb` ≈ 15, `model_dtype` `torch.float16`, and `dino_ms_per_frame_*` and `capacity_model_only_*` filled in.
- `results/hardware/probe-cuda.json` is written.
- If instead it prints `FAIL: CUDA not used`:
  - check that `uv run --group ml python -c "import torch; print(torch.__version__)"` ends in `+cu121`;
  - check that `nvidia-smi` shows the driver.

**Recorded frames: one camera, 10 s, read-only.**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acquire_recording.ps1 -CameraName vandalism -Seconds 10 -Interval 0.5 -Mkv
```

Expected:
- It prints the last recording sequences and the requested UTC interval, and whether that interval falls inside one recording sequence.
- Then: `Get-Snapshot: ~20 frames in X s ... First <ts>, last <ts>. Kind reported: Utc|Unspecified`.
- Then the MKV size and export time, and two `Next:` commands. Run both:

```powershell
uv run --group ml python aw.py footage --manifest runs\xprotect\vandalism_<UTC>\manifest.json --save
uv run --group ml python aw.py footage --mkv "<path printed>" --start <UTC printed> --sample-fps 2 --acquisition-s <s printed> --save
```

Each command reports:
- exact first and last frame timestamps against the requested range;
- duplicates and spacing;
- decode, DINOv2 and novelty ms/frame;
- peak VRAM;
- cameras sustainable at 0.5/1/2/5 fps, with and without acquisition cost.

It writes `results/hardware/footage-{snapshot,mkv}-cuda.json`. Commit those JSON files. `runs\` holds imagery and is git-ignored.

**If the snapshot object has no `DateTime`/`Bytes`:** that is UNVERIFIED in the MilestonePSTools docs, so the script deliberately stops and prints the actual properties. Send me that output and do not hand-edit timestamps.

## 2. ML direction

- **Selected task: fog/haze visibility degradation on fixed outdoor cameras.** Family 3, narrowed. The rationale table is in [visibility/preregistration.md](visibility/preregistration.md).
  - Family 1 is already solved by tracker+rule baselines, and its only open dataset is 516 GB from a single site.
  - Family 2 has no usable labelled data.
  - Camera-local vs weather discrimination is out of scope: no real labelled camera-local data exists publicly.
- **Data:**
  - Transient Attributes: CC BY 4.0, 101 fixed webcams, official camera-disjoint split, 1.8 GB.
  - External test: Digitraffic road cameras (CC BY 4.0). Labels are the co-located visibility sensor (≤ 200 m): < 1 km = fog, ≥ 5 km = clear.
- **Model:** frozen DINOv2-S (Apache-2.0) CLS+mean-patch features, then logistic regression. Trains in seconds on CPU; T4 is not a constraint.
- **Result (TA final test, 20 unseen cameras, run once): gate FAILS.** Full detail in [visibility/results.md](visibility/results.md).
  - AUPRC 0.878 vs 0.832 for zero-shot CLIP: +0.045, below the required +0.05.
  - CI [−0.04, +0.13].
  - F1 0.82 vs 0.76. AUROC 0.963.
  - Handcrafted haze cues are far weaker (AUPRC ≤ 0.58).
- **External test:** the collector has been running since 2026-10-21 14:50 local; 3 fog images in the first cycle. It is evaluated once at 50 fog images from 8 cameras, or on 2026-10-29.
  - The collector stops when this session ends. To keep it running on the Mac:
    `nohup caffeinate -i uv run --group ml python aw.py dt-collect --hours 190 >> ~/.cache/adaptive-watch/data/digitraffic/collector.log 2>&1 &`
  - It resumes from its index; check that only one copy runs.

## 3. XProtect actions: native analytics XML route

- **Technically suitable: yes, on paper.** The documented protocol is an HTTP POST of `AnalyticsEvent` XML to the Event Server's analytics port (default 9090).
  - It has **no OAuth or REST authentication**, only the allowed-address list.
  - `EventHeader/Message` must equal the configured Analytics Event name.
  - The camera is identified by FQID `ObjectId` (camera GUID) plus the camera `Kind`, or by IP in `Source/Name`.
  - Plain HTTP only; no TLS is documented. Keep it on localhost.
- **Implemented:** `scene_contracts/analytics_event.py` and `scene26.py analytics-event`, 14 tests. It provides:
  - a deterministic serializer, with a golden fixture byte-identical to `tests/fixtures/analytics-event-golden.xml`;
  - validation against Milestone's real XSD (lxml, in tests) plus a stdlib structural validator at runtime;
  - an exact `(contract, outcome) → event name` map (`config/analytics-events.json`) and an exact, unique camera-name → GUID lookup;
  - **positive-only**: negative and uncertain observations are refused;
  - a dry-run preview that prints the exact bytes and their SHA-256;
  - a send that requires that digest as approval and claims a row in SQLite **before** the POST.
- **Response handling:**
  - Empty 200 → `accepted`. This is still not a verified alarm.
  - 200 `Warning: …` → `rejected_warning`. This is treated as failure.
  - 400/403 → `rejected_http`.
  - Timeouts and 5xx → `uncertain`, which blocks any further send until an operator `reconcile`s it.
  - There is no automatic retry anywhere.
- **Remaining live verification (needs your approval and a VM run).** The first event raises a real alarm on `vandalism`:

```powershell
Get-VmsCamera | Select-Object Name, Id | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 cameras.local.json
uv run --frozen python scene26.py analytics-event preview --manual-test --test-id xml-001 --message "H26 Visually Observed Damage" --camera vandalism --camera-map cameras.local.json --at 2026-10-22T09:00:00Z
# Review the XML. Only if you approve, send exactly once with the printed digest:
uv run --frozen python scene26.py analytics-event send --manual-test --test-id xml-001 --message "H26 Visually Observed Damage" --camera vandalism --camera-map cameras.local.json --at 2026-10-22T09:00:00Z --target 127.0.0.1:9090 --approve <12+ hex digits>
```

  - **Verified** means an empty 200 **and** an alarm in Smart Client Alarm Manager on `vandalism`.
  - If the reply is `Warning: Device not known`:
    - Do not resend.
    - Next try `--server-id <recording server GUID>` with a new `--test-id`, or else identity by IP in `Source/Name`. The latter is not implemented.
  - If the reply is `Warning: Event message not known`: the name differs from the configured Analytics Event. Fix `--message`.
  - Unknown: whether the analytics port listens on 9090 here, and whether this address is on the allowed list. A 403 or refused connection answers that; **do not change firewall or Analytics Events settings** to fix it.

## 4. Decision

**Narrow scope; do not advance the trained model as a demonstrated improvement.**

- **ML:** keep visibility as the single ML task.
  - The trained head is deployable (Apache-2.0) and at least as good as zero-shot CLIP on unseen cameras, but it is **not proven better**.
  - The pre-registered external highway test decides whether it earns its place: AUROC ≥ 0.80 and above CLIP.
  - If it fails, the hybrid system should not claim a trained component.
  - Do not re-tune on the TA test.
- **T4/XProtect:** blocked only on running the runbook above. That gives the first real numbers.
- **Native events:** advance to one approved manual test event. Wire it to observations only after a verified alarm.

## 5. Reproduction

```bash
uv sync --group ml
uv run --group ml python -m unittest discover -s tests          # 73 tests
uv run --with lxml==5.3.0 python -m unittest tests.test_analytics_event   # adds the real-XSD check
uv run --group ml python vis.py extract && uv run --group ml python vis.py select
uv run --group ml python vis.py test --rerun                    # documented re-run only; reproduces test.json
```

Data stays outside Git, under `~/.cache/adaptive-watch/data/{transattr,digitraffic}`.

Transient Attributes archives (SHA-256):

| file | SHA-256 |
|---|---|
| aligned_images.tar | `2848439acd10fdb9761ee54be47003da5f68463ac1145dbcaad1a462e6ad2e62` |
| annotations.tar | `d80ceb2c54fb278a61c864b992bf276543c7e5a71ebae2c95c94ac9346ee8a55` |
| training_test_splits.tar | `c757bbe51cf0d04440e05aa42ef798cd0f52658b0229779a071aa76770b062f9` |

Attribution: Digitraffic data is "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY".
