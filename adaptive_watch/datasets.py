"""Benchmark datasets, their verified downloads and the pre-registered splits.

Raw data lives outside Git under AW_DATA (default ~/.cache/adaptive-watch/data).
Splits are at the original video-sequence level; see
docs/adaptive-watch/preregistration.md.
"""

from __future__ import annotations

import hashlib
import os
import re
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

DATA_ROOT = Path(os.environ.get("AW_DATA", Path.home() / ".cache" / "adaptive-watch" / "data"))

PED2_URL = "http://www.svcl.ucsd.edu/projects/anomaly/UCSD_Anomaly_Dataset.tar.gz"
PED2_MD5 = "5006421b89885f45a6f93b041145f2eb"  # published on the dataset page
AVENUE_BASE = "http://www.cse.cuhk.edu.hk/leojia/projects/detectabnormal/"
# No checksum is published for Avenue; these were recorded on first download (2026-10-21).
AVENUE_SHA256 = {
    "Avenue_Dataset.zip": "fc9cb8432a11ca79c18aa180c72524011411b69d3b0ff27c8816e41c0de61531",
    "ground_truth_demo.zip": "60fec1728ec8f73a58aad3aeb5729d70a805a47e0b8eb4bf91ab67ef06386d77",
}


@dataclass(frozen=True)
class Sequence:
    name: str
    fps: float  # effective rate of the frames yielded (after any subsampling)
    labels: np.ndarray | None  # bool per yielded frame; None for normal-only training clips
    frames: Callable[[], Iterator[np.ndarray]]  # yields HxWx3 uint8 RGB


@dataclass(frozen=True)
class Split:
    memory: list[str]  # normal clips fitted as the camera's memory bank
    val_normal: list[str]  # held-out normal clips for calibration
    val: list[str]  # annotated clips used for configuration choice
    test_normal: list[str]  # held-out normal clips reported with the final test
    test: list[str]  # annotated clips, evaluated once with the frozen configuration


SPLITS = {
    "ped2": Split(
        memory=[f"Train{i:03d}" for i in range(1, 13)],
        val_normal=["Train013", "Train014"],
        val=[f"Test{i:03d}" for i in range(1, 5)],
        test_normal=["Train015", "Train016"],
        test=[f"Test{i:03d}" for i in range(5, 13)],
    ),
    "avenue": Split(
        memory=[f"train{i:02d}" for i in range(1, 15)],
        val_normal=["train15"],
        val=[f"test{i:02d}" for i in range(1, 8)],
        test_normal=["train16"],
        test=[f"test{i:02d}" for i in range(8, 22)],
    ),
}

# Window length in yielded frames, chosen to be ~2 s of footage.
WINDOW = {"ped2": 16, "avenue": 10}
# Avenue is 25 fps; every 5th frame is scored (5 fps effective).
AVENUE_STRIDE = 5
# The UCSD page does not state a frame rate. 10 fps is the commonly assumed value;
# it only affects per-hour conversions, which are labelled as assumptions.
PED2_ASSUMED_FPS = 10.0


def _digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)


def _safe_members(names: list[str]) -> None:
    for n in names:
        if n.startswith("/") or ".." in Path(n).parts:
            raise ValueError(f"unsafe archive member: {n}")


def fetch(name: str) -> None:
    if name == "ped2":
        archive = DATA_ROOT / "UCSD_Anomaly_Dataset.tar.gz"
        _download(PED2_URL, archive)
        if (got := _digest(archive, "md5")) != PED2_MD5:
            raise ValueError(f"UCSD archive md5 {got} != published {PED2_MD5}")
        if not _ped2_root().exists():
            with tarfile.open(archive) as t:
                _safe_members(t.getnames())
                t.extractall(DATA_ROOT, filter="data")
    elif name == "avenue":
        root = DATA_ROOT / "avenue"
        for fname, expected in AVENUE_SHA256.items():
            path = root / fname
            _download(AVENUE_BASE + fname, path)
            got = _digest(path, "sha256")
            if expected and got != expected:
                raise ValueError(f"{fname} sha256 {got} != recorded {expected}")
            print(f"{fname} sha256 {got}")
            with zipfile.ZipFile(path) as z:
                _safe_members(z.namelist())
                if not all((root / n).exists() for n in z.namelist()):
                    z.extractall(root)
    else:
        raise KeyError(name)


# --- UCSD Ped2 ---------------------------------------------------------------

def _ped2_root() -> Path:
    return DATA_ROOT / "UCSD_Anomaly_Dataset.v1p2" / "UCSDped2"


def ped2_ground_truth() -> dict[str, np.ndarray]:
    """Parse UCSDped2.m `gt_frame = [a:b]` ranges (1-based, inclusive) per test clip."""
    text = (_ped2_root() / "Test" / "UCSDped2.m").read_text()
    out = {}
    for i, body in enumerate(re.findall(r"gt_frame\s*=\s*\[([^\]]*)\]", text), start=1):
        name = f"Test{i:03d}"
        n = len(list((_ped2_root() / "Test" / name).glob("*.tif")))
        labels = np.zeros(n, dtype=bool)
        for a, b in re.findall(r"(\d+)\s*:\s*(\d+)", body):
            labels[int(a) - 1 : int(b)] = True
        out[name] = labels
    return out


def _ped2_sequence(name: str, labels: np.ndarray | None) -> Sequence:
    folder = _ped2_root() / ("Train" if name.startswith("Train") else "Test") / name

    def frames() -> Iterator[np.ndarray]:
        from PIL import Image

        for p in sorted(folder.glob("*.tif")):
            yield np.asarray(Image.open(p).convert("RGB"))

    return Sequence(name, PED2_ASSUMED_FPS, labels, frames)


# --- CUHK Avenue -------------------------------------------------------------

def _avenue_root() -> Path:
    return DATA_ROOT / "avenue"


def _avenue_video(name: str) -> Path:
    kind, idx = ("training", name[5:]) if name.startswith("train") else ("testing", name[4:])
    return _avenue_root() / "Avenue Dataset" / f"{kind}_videos" / f"{idx}.avi"


def avenue_ground_truth() -> dict[str, np.ndarray]:
    """Frame is anomalous if its annotation mask has any positive pixel; subsampled."""
    from scipy.io import loadmat

    out = {}
    for i in range(1, 22):
        mat = loadmat(_avenue_root() / "ground_truth_demo" / "testing_label_mask" / f"{i}_label.mat")
        vol = mat["volLabel"].ravel()
        full = np.array([np.asarray(m).any() for m in vol], dtype=bool)
        out[f"test{i:02d}"] = full[::AVENUE_STRIDE]
    return out


def _avenue_sequence(name: str, labels: np.ndarray | None) -> Sequence:
    path = _avenue_video(name)

    def frames() -> Iterator[np.ndarray]:
        import av

        with av.open(str(path)) as c:
            for i, f in enumerate(c.decode(video=0)):
                if i % AVENUE_STRIDE == 0:
                    yield f.to_ndarray(format="rgb24")

    return Sequence(name, 25.0 / AVENUE_STRIDE, labels, frames)


def sequences(dataset: str, names: list[str]) -> list[Sequence]:
    if dataset == "ped2":
        gt = ped2_ground_truth()
        return [_ped2_sequence(n, gt.get(n)) for n in names]
    if dataset == "avenue":
        gt = avenue_ground_truth()
        return [_avenue_sequence(n, gt.get(n)) for n in names]
    raise KeyError(dataset)
