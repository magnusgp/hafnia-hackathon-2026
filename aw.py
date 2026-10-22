"""Adaptive Watch benchmark CLI.

    uv run --group ml python aw.py fetch ped2
    uv run --group ml python aw.py extract ped2
    uv run --group ml python aw.py evaluate ped2 --phase val    # chooses + freezes config
    git add results/ped2/config.json && git commit ...           # pre-registration lock
    uv run --group ml python aw.py evaluate ped2 --phase test   # once, frozen config
    uv run --group ml python aw.py probe --require-cuda --save  # hardware / latency (T4)
    uv run --group ml python aw.py footage --manifest runs/xprotect/<clip>/manifest.json --save
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from itertools import product
from pathlib import Path

import numpy as np

from adaptive_watch import datasets, features, metrics, novelty

RESULTS = Path(__file__).parent / "results"
DINO_GRID = list(product(["max", "top1pct"], [1, 3, 5]))
MOTION_GRID = list(product(["mean", "p99"], [1, 3, 5]))


def _phase_names(split: datasets.Split, phase: str) -> tuple[list[str], list[str]]:
    return (split.val_normal, split.val) if phase == "val" else (split.test_normal, split.test)


def _committed(path: Path) -> bool:
    rel = str(path.relative_to(Path(__file__).parent))
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel]).returncode == 0
    return tracked and clean


def _signals(ds: str, names: list[str], memory: novelty.PatchMemory) -> tuple[dict, float, int]:
    """Per sequence: patch novelty grid and motion signal. Returns scoring seconds and frames."""
    out, secs, n = {}, 0.0, 0
    for name in names:
        grids, motion = features.load(ds, name)
        patch, dt = novelty.timed_patch_scores(memory, grids)
        out[name] = (patch, motion)
        secs, n = secs + dt, n + len(grids)
    return out, secs, n


def _dino(patch: np.ndarray, agg: str, length: int) -> np.ndarray:
    return novelty.smooth(novelty.aggregate(patch, agg), length)


def _motion(motion: np.ndarray, signal: str, length: int) -> np.ndarray:
    return novelty.smooth(motion[:, 0 if signal == "mean" else 1], length)


def _method_scores(cfg: dict, sig: dict) -> dict[str, dict[str, np.ndarray]]:
    out = {"dino": {}, "motion": {}, "fused": {}}
    for name, (patch, motion) in sig.items():
        d = _dino(patch, *cfg["dino"])
        m = _motion(motion, *cfg["motion"])
        out["dino"][name], out["motion"][name] = d, m
        z = cfg["fusion_norm"]
        out["fused"][name] = (d - z["dino"][0]) / z["dino"][1] + (m - z["motion"][0]) / z["motion"][1]
    return out


def _evaluate(ds: str, scores: dict[str, np.ndarray], seqs: dict[str, datasets.Sequence]) -> tuple[dict, list]:
    win_len, fps = datasets.WINDOW[ds], next(iter(seqs.values())).fps
    wins, evts, f_lab, f_sc = [], [], [], []
    for name, s in seqs.items():
        labels = s.labels if s.labels is not None else np.zeros(len(scores[name]), dtype=bool)
        if len(labels) != len(scores[name]):
            raise ValueError(f"{name}: {len(labels)} labels vs {len(scores[name])} frames")
        wins += metrics.windows(name, scores[name], labels, win_len)
        evts += metrics.events(name, labels, win_len)
        f_lab.append(labels)
        f_sc.append(scores[name])
    annotated = [n for n, s in seqs.items() if s.labels is not None]
    return {
        "frame": metrics.ranking(np.concatenate(f_lab), np.concatenate(f_sc)),
        "frame_annotated_only": metrics.ranking(
            np.concatenate([seqs[n].labels for n in annotated]), np.concatenate([scores[n] for n in annotated])
        ),
        "window": metrics.ranking(np.array([w.anomalous for w in wins]), np.array([w.score for w in wins])),
        "windows": len(wins),
        "events": len(evts),
        "footage_s": sum(len(v) for v in scores.values()) / fps,
        "budget": metrics.budget_curve(evts, wins, fps),
    }, wins


def _select_config(ds: str, sig: dict, seqs: dict, normal_names: list[str]) -> tuple[dict, dict]:
    """Pick DINOv2 and motion settings by validation window AUPRC; freeze calibration."""
    def auprc(score_fn) -> float:
        res, _ = _evaluate(ds, {n: score_fn(*sig[n]) for n in seqs}, seqs)
        return res["window"]["auprc"]

    grid = {
        "dino": {f"{a}/{l}": auprc(lambda p, m: _dino(p, a, l)) for a, l in DINO_GRID},
        "motion": {f"{a}/{l}": auprc(lambda p, m: _motion(m, a, l)) for a, l in MOTION_GRID},
    }
    best = {k: max(v, key=v.get).split("/") for k, v in grid.items()}
    cfg = {"dino": [best["dino"][0], int(best["dino"][1])], "motion": [best["motion"][0], int(best["motion"][1])]}
    norm = {}
    for key, fn in (("dino", lambda p, m: _dino(p, *cfg["dino"])), ("motion", lambda p, m: _motion(m, *cfg["motion"]))):
        v = np.concatenate([fn(*sig[n]) for n in normal_names])
        norm[key] = [float(v.mean()), float(v.std() + 1e-9)]
    cfg["fusion_norm"] = norm
    # Operating threshold: highest window score seen on held-out normal footage.
    cfg["thresholds"] = {}
    for method, sc in _method_scores(cfg, {n: sig[n] for n in normal_names}).items():
        cfg["thresholds"][method] = max(
            w.score for n in normal_names for w in metrics.windows(n, sc[n], None, datasets.WINDOW[ds])
        )
    return cfg, grid


def _examples(wins: list, k: int = 3) -> dict:
    """Highest-scoring true/false positives and lowest-scoring anomalous windows."""
    def row(w):
        return {"seq": w.seq, "frames": [w.start, w.end], "score": round(w.score, 4)}

    pos = sorted([w for w in wins if w.anomalous], key=lambda w: -w.score)
    neg = sorted([w for w in wins if not w.anomalous], key=lambda w: -w.score)
    return {"true_positive": [row(w) for w in pos[:k]], "false_positive": [row(w) for w in neg[:k]],
            "missed_lowest": [row(w) for w in pos[-k:]]}


def cmd_evaluate(args) -> None:
    ds, phase = args.dataset, args.phase
    split = datasets.SPLITS[ds]
    out_dir = RESULTS / ds
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = out_dir / "config.json"
    if phase == "test":
        if not _committed(cfg_path):
            sys.exit(f"{cfg_path} must be committed (and unmodified) before the final test.")
        if (out_dir / "test.json").exists() and not args.rerun:
            sys.exit("test.json exists; final test is run once. Use --rerun to record a documented re-run.")

    normal_names, ann_names = _phase_names(split, phase)
    seqs = {s.name: s for s in datasets.sequences(ds, normal_names + ann_names)}
    memory = novelty.PatchMemory([features.load(ds, n)[0] for n in split.memory])
    sig, score_s, n_frames = _signals(ds, list(seqs), memory)

    report = {"dataset": ds, "phase": phase, "split": {"memory": split.memory, "normal": normal_names,
              "annotated": ann_names}, "memory_frames": memory.n_frames}
    if phase == "val":
        cfg, grid = _select_config(ds, sig, seqs, normal_names)
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
        report["grid_window_auprc"] = grid
    else:
        cfg = json.loads(cfg_path.read_text())
        report["config_commit"] = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(cfg_path)], capture_output=True, text=True
        ).stdout.strip()
    report["config"] = cfg

    report["methods"] = {}
    for method, scores in _method_scores(cfg, sig).items():
        res, wins = _evaluate(ds, scores, seqs)
        res["operating_point"] = metrics.threshold_stats(
            [e for n in ann_names for e in metrics.events(n, seqs[n].labels, datasets.WINDOW[ds])], wins,
            cfg["thresholds"][method], seqs[ann_names[0]].fps)
        res["examples"] = _examples(wins)
        report["methods"][method] = res

    timings = [json.loads((features.CACHE_ROOT / ds / f"{n}.timing.json").read_text()) for n in seqs]
    tf = sum(t["frames"] for t in timings)
    report["latency"] = {
        "device": memory.device.type,
        "decode_ms_per_frame": 1000 * sum(t["decode_s"] for t in timings) / tf,
        "dino_ms_per_frame": 1000 * sum(t["dino_s"] for t in timings) / tf,
        "novelty_ms_per_frame": 1000 * score_s / n_frames,
    }
    name = "test.json" if phase == "test" else "val.json"
    (out_dir / name).write_text(json.dumps(report, indent=2) + "\n")
    print(summary(report))


def summary(r: dict) -> str:
    lines = [f"## {r['dataset']} / {r['phase']}", "",
             "| method | frame AUROC | frame AUPRC | window AUROC | window AUPRC | recall@30% | periodic@30% | random@30% | prec@30% | op. sel. | op. recall | op. false/normal-h |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    f = lambda x: "–" if x is None else f"{x:.3f}"
    for m, res in r["methods"].items():
        b = res["budget"]["0.30"]
        op = res["operating_point"]
        lines.append(f"| {m} | {f(res['frame']['auroc'])} | {f(res['frame']['auprc'])} | {f(res['window']['auroc'])} | "
                     f"{f(res['window']['auprc'])} | {f(b['model']['event_recall'])} | {f(b['periodic'].get('event_recall'))} | "
                     f"{f(b['random'].get('event_recall'))} | {f(b['model']['window_precision'])} | {f(op['selected_fraction'])} | "
                     f"{f(op['event_recall'])} | {f(op['false_alerts_per_normal_hour'])} |")
    return "\n".join(lines)


def cmd_probe(args) -> None:
    """Hardware report and DINOv2 throughput on synthetic frames (no dataset needed)."""
    import platform

    import torch

    from adaptive_watch import footage

    info = {"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda,
            "cuda_available": torch.cuda.is_available()}
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        free, total = torch.cuda.mem_get_info()
        info.update(gpu=p.name, vram_gb=round(p.total_memory / 2**30, 2), capability=f"{p.major}.{p.minor}",
                    vram_free_gb_before=round(free / 2**30, 2), cudnn=torch.backends.cudnn.version())
    try:
        info["nvidia_smi"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["nvidia_smi"] = None
    ext = features.DinoExtractor()
    info["device"] = ext.device.type
    info["model_dtype"] = str(ext.dtype)
    if args.require_cuda and ext.device.type != "cuda":
        print(json.dumps(info, indent=2))
        sys.exit("FAIL: CUDA not used (CPU/MPS fallback). Check `nvidia-smi` and that torch is the cu121 wheel.")
    rng = np.random.default_rng(0)
    for res in args.resolutions.split(","):
        w, h = (int(v) for v in res.split("x"))
        frames = rng.integers(0, 255, (args.batch, h, w, 3), dtype=np.uint8)
        ext(frames)  # warm-up
        features._sync(ext.device)
        t0 = time.perf_counter()
        for _ in range(args.iters):
            grids = ext(frames)
        features._sync(ext.device)
        info[f"dino_ms_per_frame_{w}x{h}"] = 1000 * (time.perf_counter() - t0) / (args.iters * args.batch)
    memory = novelty.PatchMemory([np.repeat(grids, 1340 // args.batch * novelty.MEMORY_STRIDE, axis=0)])
    _, dt = novelty.timed_patch_scores(memory, np.repeat(grids, 4, axis=0))
    info["novelty_ms_per_frame_1340_memory_frames"] = 1000 * dt / (4 * args.batch)
    # Synthetic: no decode/acquisition cost. `aw.py footage` measures real recordings end to end.
    for res in args.resolutions.split(","):
        info[f"capacity_model_only_{res}"] = footage.capacity(
            info[f"dino_ms_per_frame_{res}"] + info["novelty_ms_per_frame_1340_memory_frames"])
    if ext.device.type == "cuda":
        info["peak_vram_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    print(json.dumps(info, indent=2))
    if args.save:
        out = RESULTS / "hardware"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"probe-{ext.device.type}.json").write_text(json.dumps(info, indent=2) + "\n")


def cmd_footage(args) -> None:
    """Real recorded footage -> tensors: exact timestamps, decode/model latency, throughput."""
    from adaptive_watch import footage

    t_total = time.perf_counter()
    if args.manifest:
        frames, meta = footage.snapshot_frames(Path(args.manifest))
        m = meta["manifest"]
        source = {"path": "Get-Snapshot JPEG", "camera_name": m.get("camera_name"),
                  "acquisition_s": m.get("elapsed_s"), "pstools_version": m.get("pstools_version")}
        start, end = footage.parse_utc(m["requested_start_utc"]), footage.parse_utc(m["requested_end_utc"])
    else:
        start = footage.parse_utc(args.start)
        frames, meta = footage.mkv_frames(Path(args.mkv), start, args.sample_fps)
        source = {"path": "MKV export", "codec": meta["codec"], "decoded_frames": meta["decoded_frames"],
                  "sample_fps": args.sample_fps, "acquisition_s": args.acquisition_s}
        end = footage.parse_utc(args.end) if args.end else None
    if not frames:
        sys.exit("No frames decoded.")
    report = {"source": source,
              "timestamps": footage.timestamp_report([f.timestamp for f in frames], start, end),
              "decode_ms_per_frame": 1000 * meta["decode_s"] / len(frames)}
    report["model"] = footage.process(frames, batch=args.batch)
    report["end_to_end_wall_s"] = time.perf_counter() - t_total
    per_frame = report["decode_ms_per_frame"] + report["model"]["dino_ms_per_frame"] + \
        report["model"]["novelty_ms_per_frame"]
    report["decode_plus_model_ms_per_frame"] = per_frame
    report["capacity_excluding_acquisition"] = footage.capacity(per_frame)
    if source.get("acquisition_s"):
        report["acquisition_ms_per_frame"] = 1000 * source["acquisition_s"] / len(frames)
        report["capacity_including_acquisition"] = footage.capacity(per_frame + report["acquisition_ms_per_frame"])
    print(json.dumps(report, indent=2))
    if args.save:
        out = RESULTS / "hardware"
        out.mkdir(parents=True, exist_ok=True)
        tag = "snapshot" if args.manifest else "mkv"
        (out / f"footage-{tag}-{report['model']['device']}.json").write_text(json.dumps(report, indent=2) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("dataset", choices=sorted(datasets.SPLITS))
    e = sub.add_parser("extract")
    e.add_argument("dataset", choices=sorted(datasets.SPLITS))
    e.add_argument("--force", action="store_true")
    v = sub.add_parser("evaluate")
    v.add_argument("dataset", choices=sorted(datasets.SPLITS))
    v.add_argument("--phase", choices=["val", "test"], required=True)
    v.add_argument("--rerun", action="store_true")
    pr = sub.add_parser("probe")
    pr.add_argument("--batch", type=int, default=16)
    pr.add_argument("--iters", type=int, default=5)
    pr.add_argument("--save", action="store_true")
    pr.add_argument("--resolutions", default="640x360,1920x1080")
    pr.add_argument("--require-cuda", action="store_true", help="exit non-zero on CPU/MPS fallback")
    fo = sub.add_parser("footage", help="process real recorded XProtect footage (read-only, local files)")
    src = fo.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest", help="manifest.json written by scripts/acquire_recording.ps1")
    src.add_argument("--mkv", help="MKV exported by scripts/acquire_recording.ps1 -Mkv")
    fo.add_argument("--start", help="UTC start of the MKV export (required with --mkv)")
    fo.add_argument("--end", help="Actual requested UTC export end; never substitute the last decoded frame")
    fo.add_argument("--sample-fps", type=float, default=2.0, help="MKV only: frames kept per second")
    fo.add_argument("--acquisition-s", type=float, help="MKV only: Start-Export wall time printed by the script")
    fo.add_argument("--batch", type=int, default=16)
    fo.add_argument("--save", action="store_true")
    dc = sub.add_parser("dt-collect", help="poll Finnish road weather cameras + visibility sensors (CC BY 4.0)")
    dc.add_argument("--hours", type=float, default=240.0)
    dc.add_argument("--interval", type=int, default=600)
    a = p.parse_args()
    if a.cmd == "footage" and a.mkv and not a.start:
        p.error("--mkv requires --start (UTC export start)")
    if a.cmd == "fetch":
        datasets.fetch(a.dataset)
    elif a.cmd == "extract":
        s = datasets.SPLITS[a.dataset]
        names = s.memory + s.val_normal + s.val + s.test_normal + s.test
        features.extract(a.dataset, datasets.sequences(a.dataset, names), force=a.force)
    elif a.cmd == "evaluate":
        cmd_evaluate(a)
    elif a.cmd == "footage":
        cmd_footage(a)
    elif a.cmd == "dt-collect":
        from adaptive_watch import digitraffic

        digitraffic.collect(a.hours, a.interval)
    else:
        cmd_probe(a)


if __name__ == "__main__":
    main()
