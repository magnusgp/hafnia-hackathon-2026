"""Frozen DINOv2-S/14 patch embeddings and a frame-difference motion signal.

Features are cached per sequence under AW_CACHE (default ~/.cache/adaptive-watch/features).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

from .datasets import Sequence

# DINOv2's positional-embedding interpolation (bicubic) has no MPS kernel; it is tiny,
# so let it fall back to CPU on Apple silicon. No effect on CUDA or CPU.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

DINO_MODEL = "facebook/dinov2-small"
DINO_REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"  # Apache-2.0
INPUT_HEIGHT = 224  # 16 patches of 14 px; width keeps the camera's aspect ratio
CACHE_ROOT = Path(os.environ.get("AW_CACHE", Path.home() / ".cache" / "adaptive-watch" / "features"))
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def device():
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def input_size(height: int, width: int) -> tuple[int, int]:
    return INPUT_HEIGHT, max(14, round(width * INPUT_HEIGHT / height / 14) * 14)


class DinoExtractor:
    def __init__(self, dev=None):
        import torch
        from transformers import Dinov2Model

        self.torch = torch
        self.device = dev or device()
        self.dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        self.model = (
            Dinov2Model.from_pretrained(DINO_MODEL, revision=DINO_REVISION, torch_dtype=self.dtype)
            .to(self.device)
            .eval()
        )

    def __call__(self, frames: np.ndarray) -> np.ndarray:
        """uint8 [B,H,W,3] -> L2-normalised float16 patch grid [B,h,w,384]."""
        torch = self.torch
        b, h, w, _ = frames.shape
        th, tw = input_size(h, w)
        # Resize on CPU on every device: identical preprocessing, and MPS lacks antialiasing.
        x = torch.from_numpy(frames).permute(0, 3, 1, 2).float() / 255.0
        x = torch.nn.functional.interpolate(x, size=(th, tw), mode="bilinear", antialias=True, align_corners=False)
        x = (x - torch.from_numpy(_MEAN)[:, None, None]) / torch.from_numpy(_STD)[:, None, None]
        with torch.inference_mode():
            tokens = self.model(pixel_values=x.to(self.device, self.dtype)).last_hidden_state[:, 1:]
        tokens = torch.nn.functional.normalize(tokens.float(), dim=-1)
        return tokens.reshape(b, th // 14, tw // 14, -1).half().cpu().numpy()

    def embed(self, frames: np.ndarray) -> np.ndarray:
        """uint8 [B,H,W,3] -> global descriptor [B,768]: CLS token ++ mean patch token (unnormalised)."""
        torch = self.torch
        b, h, w, _ = frames.shape
        th, tw = input_size(h, w)
        x = torch.from_numpy(frames).permute(0, 3, 1, 2).float() / 255.0
        x = torch.nn.functional.interpolate(x, size=(th, tw), mode="bilinear", antialias=True, align_corners=False)
        x = (x - torch.from_numpy(_MEAN)[:, None, None]) / torch.from_numpy(_STD)[:, None, None]
        with torch.inference_mode():
            hidden = self.model(pixel_values=x.to(self.device, self.dtype)).last_hidden_state.float()
        return torch.cat([hidden[:, 0], hidden[:, 1:].mean(1)], dim=1).cpu().numpy()


def motion_signal(prev: np.ndarray, cur: np.ndarray) -> tuple[float, float]:
    """Mean and 99th-percentile absolute grey-level difference between consecutive frames."""
    d = np.abs(cur.mean(axis=2) - prev.mean(axis=2))
    return float(d.mean()), float(np.percentile(d, 99))


def _sync(dev) -> None:
    import torch

    if dev.type == "cuda":
        torch.cuda.synchronize()
    elif dev.type == "mps":
        torch.mps.synchronize()


def extract(dataset: str, seqs: list[Sequence], batch: int = 16, force: bool = False) -> None:
    """Cache DINOv2 patch grids and motion signals; record wall-clock timing."""
    out = CACHE_ROOT / dataset
    out.mkdir(parents=True, exist_ok=True)
    todo = [s for s in seqs if force or not (out / f"{s.name}.dino.npy").exists()]
    if not todo:
        return
    ext = DinoExtractor()
    for s in todo:
        frames: list[np.ndarray] = []
        t0 = time.perf_counter()
        for f in s.frames():
            frames.append(f)
        decode_s = time.perf_counter() - t0
        stack = np.stack(frames)
        grids = []
        t0 = time.perf_counter()
        for i in range(0, len(stack), batch):
            grids.append(ext(stack[i : i + batch]))
        _sync(ext.device)
        model_s = time.perf_counter() - t0
        motion = np.array([(0.0, 0.0)] + [motion_signal(a, b) for a, b in zip(stack[:-1], stack[1:])])
        motion[0] = motion[1] if len(motion) > 1 else motion[0]
        np.save(out / f"{s.name}.dino.npy", np.concatenate(grids))
        np.save(out / f"{s.name}.motion.npy", motion.astype(np.float32))
        (out / f"{s.name}.timing.json").write_text(
            json.dumps({"frames": len(stack), "decode_s": decode_s, "dino_s": model_s,
                        "device": ext.device.type, "batch": batch, "shape": list(stack.shape[1:])})
        )
        print(f"{dataset}/{s.name}: {len(stack)} frames, decode {decode_s:.2f}s, dino {model_s:.2f}s on {ext.device.type}")


def load(dataset: str, name: str) -> tuple[np.ndarray, np.ndarray]:
    d = CACHE_ROOT / dataset
    return np.load(d / f"{name}.dino.npy"), np.load(d / f"{name}.motion.npy")
