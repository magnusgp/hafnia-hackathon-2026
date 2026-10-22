"""Recorded XProtect footage -> timestamped RGB tensors, with per-stage timing.

Two read-only acquisition paths produce the input (see scripts/acquire_recording.ps1):

- Get-Snapshot JPEGs plus a manifest.json that lists each frame's recorded timestamp.
- An MKV export (Start-Export -Format MKV); timestamps are export start + stream PTS.

Nothing here talks to XProtect. Camera GUIDs never enter the report.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Frame:
    timestamp: datetime  # recorded time (UTC) reported by the Recording Server or derived from PTS
    rgb: np.ndarray  # HxWx3 uint8


def parse_utc(value: str) -> datetime:
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError(f"timestamp without UTC offset: {value!r}")
    return t.astimezone(timezone.utc)


def load_manifest(path: Path) -> dict:
    """Validate a Get-Snapshot manifest; frame files must sit next to it."""
    m = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if m.get("source") not in {"Get-Snapshot", "Start-Export"}:
        raise ValueError("manifest.source must be Get-Snapshot or Start-Export")
    if m["source"] == "Get-Snapshot":
        frames = m.get("frames")
        if not isinstance(frames, list) or not frames:
            raise ValueError("manifest lists no frames")
        times = [parse_utc(f["timestamp_utc"]) for f in frames]
        if any(b < a for a, b in zip(times, times[1:])):
            raise ValueError("frame timestamps are not monotonic")
        for f in frames:
            if Path(f["file"]).name != f["file"]:
                raise ValueError(f"frame file must be a bare name: {f['file']!r}")
    return m


def timestamp_report(times: list[datetime], start: datetime, end: datetime | None) -> dict:
    """Exact first/last timestamps, spacing and duplicates: shows what the server actually returned."""
    gaps = np.diff([t.timestamp() for t in times]) if len(times) > 1 else np.array([])
    return {
        "frames": len(times),
        "first_utc": times[0].isoformat().replace("+00:00", "Z"),
        "last_utc": times[-1].isoformat().replace("+00:00", "Z"),
        "requested_start_utc": start.isoformat().replace("+00:00", "Z"),
        "requested_end_utc": end.isoformat().replace("+00:00", "Z") if end else None,
        "end_provenance": "caller_supplied_requested_end" if end else "unknown_requested_end",
        "decoded_last_minus_requested_end_s": (times[-1]-end).total_seconds() if end else None,
        "outside_requested_range": sum(not (start <= t <= end) for t in times) if end else None,
        "duplicate_timestamps": int((gaps == 0).sum()),
        "spacing_s": None if not len(gaps) else {
            "min": float(gaps.min()), "median": float(np.median(gaps)), "max": float(gaps.max())},
    }


def snapshot_frames(manifest_path: Path) -> tuple[list[Frame], dict]:
    from PIL import Image

    m = load_manifest(manifest_path)
    root = Path(manifest_path).parent
    out, t0 = [], time.perf_counter()
    for f in m["frames"]:
        with Image.open(root / f["file"]) as im:
            out.append(Frame(parse_utc(f["timestamp_utc"]), np.asarray(im.convert("RGB"))))
    return out, {"decode_s": time.perf_counter() - t0, "manifest": m}


def mkv_frames(path: Path, start: datetime, sample_fps: float | None) -> tuple[list[Frame], dict]:
    """Decode an exported MKV, keeping at most `sample_fps` frames per second of footage."""
    import av

    out, t0, next_t, decoded = [], time.perf_counter(), 0.0, 0
    with av.open(str(path)) as c:
        stream = c.streams.video[0]
        codec = stream.codec_context.name
        for fr in c.decode(stream):
            decoded += 1
            if fr.pts is None:
                raise ValueError("MKV frame without PTS; cannot timestamp it")
            rel = float(fr.pts * stream.time_base)
            if sample_fps and rel + 1e-6 < next_t:
                continue
            # Fixed grid (k / sample_fps), so the kept spacing does not drift with frame jitter.
            while sample_fps and next_t <= rel + 1e-6:
                next_t += 1.0 / sample_fps
            out.append(Frame(start + timedelta(seconds=rel), fr.to_ndarray(format="rgb24")))
    return out, {"decode_s": time.perf_counter() - t0, "decoded_frames": decoded, "codec": codec}


def process(frames: list[Frame], batch: int = 16, memory_fraction: float = 0.5) -> dict:
    """Run the real tensor path on footage: DINOv2 patch grids, then novelty against the earliest frames.

    The memory here is only a latency stand-in (first part of the same clip); it is not a
    detector evaluation and its scores are not reported.
    """
    import torch

    from . import features, novelty

    if len(frames) < 4:
        raise ValueError("need at least 4 frames")
    shapes = {f.rgb.shape for f in frames}
    if len(shapes) != 1:
        raise ValueError(f"mixed frame shapes: {sorted(shapes)}")
    ext = features.DinoExtractor()
    stack = np.stack([f.rgb for f in frames])
    ext(stack[: min(batch, len(stack))])  # warm-up
    features._sync(ext.device)
    if ext.device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    grids = np.concatenate([ext(stack[i : i + batch]) for i in range(0, len(stack), batch)])
    features._sync(ext.device)
    dino_s = time.perf_counter() - t0
    split = max(2, int(len(grids) * memory_fraction))
    memory = novelty.PatchMemory([grids[:split]], dev=ext.device)
    _, nov_s = novelty.timed_patch_scores(memory, grids[split:])
    report = {
        "device": ext.device.type,
        "frame_shape": list(stack.shape[1:]),
        "tensor_grid_shape": list(grids.shape[1:]),
        "batch": batch,
        "dino_ms_per_frame": 1000 * dino_s / len(grids),
        "novelty_ms_per_frame": 1000 * nov_s / (len(grids) - split),
        "novelty_memory_frames": memory.n_frames,
    }
    if ext.device.type == "cuda":
        report["peak_vram_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 3)
    return report


def capacity(ms_per_frame: float, rates=(0.5, 1.0, 2.0, 5.0)) -> dict:
    """Cameras one device sustains at each sampling rate, from measured per-frame cost."""
    fps = 1000.0 / ms_per_frame
    return {"frames_per_s": fps, "cameras_at_fps": {str(r): round(fps / r, 1) for r in rates}}
