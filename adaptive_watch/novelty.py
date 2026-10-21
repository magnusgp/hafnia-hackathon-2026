"""Camera-specific novelty: position-conditioned nearest-neighbour patch memory.

For a fixed camera, the patch at grid cell (i, j) is compared only with normal
training patches from the same cell and its 8 neighbours. Patch novelty is
1 - max cosine similarity. Nothing is trained; the fitted state is the memory.
"""

from __future__ import annotations

import time

import numpy as np

NEIGHBOURHOOD = 1  # 3x3 cells
MEMORY_STRIDE = 2  # every 2nd normal frame enters the memory


class PatchMemory:
    def __init__(self, normal_grids: list[np.ndarray], dev=None):
        import torch

        from .features import device

        self.torch = torch
        self.device = dev or device()
        # Half precision only on CUDA; MPS/CPU matmul in fp32.
        self.dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        bank = np.concatenate([g[::MEMORY_STRIDE] for g in normal_grids])  # [N,h,w,D]
        self.n_frames = len(bank)
        self.memory = torch.from_numpy(bank).to(self.device, self.dtype).permute(1, 2, 3, 0).contiguous()  # [h,w,D,N]

    def patch_scores(self, grids: np.ndarray, batch: int = 8) -> np.ndarray:
        """[T,h,w,D] -> patch novelty [T,h,w]."""
        torch = self.torch
        h, w = self.memory.shape[:2]
        out = []
        for i in range(0, len(grids), batch):
            q = torch.from_numpy(grids[i : i + batch]).to(self.device, self.dtype)  # [B,h,w,D]
            best = torch.full(q.shape[:3], -2.0, device=self.device, dtype=torch.float32)
            for dy in range(-NEIGHBOURHOOD, NEIGHBOURHOOD + 1):
                for dx in range(-NEIGHBOURHOOD, NEIGHBOURHOOD + 1):
                    ys, yd = slice(max(0, dy), h + min(0, dy)), slice(max(0, -dy), h + min(0, -dy))
                    xs, xd = slice(max(0, dx), w + min(0, dx)), slice(max(0, -dx), w + min(0, -dx))
                    # query at (y, x) vs memory at (y + dy, x + dx)
                    sim = torch.einsum("bhwd,hwdn->bhwn", q[:, yd, xd], self.memory[ys, xs]).amax(-1).float()
                    best[:, yd, xd] = torch.maximum(best[:, yd, xd], sim)
            out.append((1.0 - best).cpu().numpy())
        return np.concatenate(out)


def aggregate(patch: np.ndarray, how: str) -> np.ndarray:
    """Patch novelty [T,h,w] -> frame score [T]."""
    flat = patch.reshape(len(patch), -1)
    if how == "max":
        return flat.max(1)
    if how == "top1pct":
        k = max(1, flat.shape[1] // 100)
        return np.sort(flat, axis=1)[:, -k:].mean(1)
    raise KeyError(how)


def smooth(scores: np.ndarray, length: int) -> np.ndarray:
    """Causal moving average: each frame uses only itself and earlier frames."""
    if length <= 1:
        return scores.astype(np.float64)
    c = np.cumsum(np.concatenate([[0.0], scores]))
    idx = np.arange(1, len(scores) + 1)
    lo = np.maximum(0, idx - length)
    return (c[idx] - c[lo]) / (idx - lo)


def timed_patch_scores(memory: PatchMemory, grids: np.ndarray) -> tuple[np.ndarray, float]:
    from .features import _sync

    t0 = time.perf_counter()
    s = memory.patch_scores(grids)
    _sync(memory.device)
    return s, time.perf_counter() - t0
