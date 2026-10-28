"""Fog / haze visibility degradation on fixed outdoor cameras (docs/research/visibility/preregistration.md).

Data: Transient Attributes (CC BY 4.0) for training/selection/test, Digitraffic (CC BY 4.0)
as an external real-weather test. Features are cached per image under AW_CACHE.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .datasets import DATA_ROOT
from .features import CACHE_ROOT

TA_ROOT = DATA_ROOT / "transattr"
FEATURES = CACHE_ROOT / "visibility"
POS, NEG = 0.6, 0.3  # fog score thresholds; in between is excluded
SECONDARY = ("night", "rain", "snow")
CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
CLIP_PROMPTS = ("a photo of a foggy scene with low visibility", "a photo of a clear scene with good visibility")
HANDCRAFTED = ("dark_channel", "neg_contrast", "neg_log_laplacian", "luminance", "saturation")
BASELINES = {"B1": "dark_channel", "B2": "neg_contrast", "B3": "neg_log_laplacian"}  # fixed direction


@dataclass(frozen=True)
class Item:
    name: str  # dataset-relative image path; also the cache key
    camera: str
    path: Path
    label: int | None  # 1 fog, 0 clear, None excluded
    attrs: dict  # raw attribute scores (fog + secondary), for reporting


def ta_items() -> dict[str, list[Item]]:
    """Pre-registered camera-level splits: fit / val (every 5th sorted training camera) / test."""
    attrs = (TA_ROOT / "annotations" / "attributes.txt").read_text().split()
    keep = ("fog",) + SECONDARY
    rows = {}
    for line in (TA_ROOT / "annotations" / "annotations.tsv").read_text().splitlines():
        name, *vals = line.split("\t")
        scores = [float(v.split(",")[0]) for v in vals]
        rows[name] = {a: scores[attrs.index(a)] for a in keep}
    split = {s: [n.strip() for n in (TA_ROOT / "holdout_split" / f"{f}.txt").read_text().split() if n.strip()]
             for s, f in (("train", "training"), ("test", "test"))}
    train_cams = sorted({n.split("/")[0] for n in split["train"]})
    val_cams = set(train_cams[::5])

    def item(n):
        fog = rows[n]["fog"]
        label = 1 if fog >= POS else 0 if fog <= NEG else None
        return Item(n, n.split("/")[0], TA_ROOT / "imageAlignedLD" / n, label, rows[n])

    out = {"fit": [], "val": [], "test": [item(n) for n in split["test"]]}
    for n in split["train"]:
        out["val" if n.split("/")[0] in val_cams else "fit"].append(item(n))
    return out


def dt_items() -> list[Item]:
    from .digitraffic import ROOT

    out = []
    for line in (ROOT / "index.jsonl").read_text().splitlines():
        r = json.loads(line)
        out.append(Item("dt/" + r["file"], r["camera"], ROOT / "images" / r["file"], int(r["label"]),
                        {"visibility_m": r["visibility_m"], "captured": r["captured"]}))
    return out


def load_rgb(path: Path, height: int | None = None) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        if height and im.height != height:
            im = im.resize((max(1, round(im.width * height / im.height)), height), Image.BILINEAR)
        return np.asarray(im)


def handcrafted(rgb: np.ndarray) -> np.ndarray:
    """Haze/visibility cues: dark channel, contrast, sharpness, luminance, saturation."""
    from scipy import ndimage

    x = rgb.astype(np.float32) / 255.0
    lum = 0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2]
    dark = ndimage.minimum_filter(x.min(axis=2), size=15)
    mx, mn = x.max(axis=2), x.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    lap = ndimage.laplace(lum)
    return np.array([dark.mean(), -lum.std(), -np.log(lap.var() + 1e-8), lum.mean(), sat.mean()], dtype=np.float32)


class Clip:
    def __init__(self, dev):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.torch, self.device = torch, dev
        self.model = CLIPModel.from_pretrained(CLIP_MODEL, revision=CLIP_REVISION).to(dev).eval()
        self.proc = CLIPProcessor.from_pretrained(CLIP_MODEL, revision=CLIP_REVISION)
        with torch.inference_mode():
            t = self.proc(text=list(CLIP_PROMPTS), return_tensors="pt", padding=True).to(dev)
            self.text = torch.nn.functional.normalize(self.model.get_text_features(**t), dim=-1)

    def fog_prob(self, images: list[np.ndarray]) -> np.ndarray:
        torch = self.torch
        with torch.inference_mode():
            px = self.proc(images=images, return_tensors="pt")["pixel_values"].to(self.device)
            img = torch.nn.functional.normalize(self.model.get_image_features(pixel_values=px), dim=-1)
            logits = self.model.logit_scale.exp() * img @ self.text.T
            return logits.softmax(-1)[:, 0].cpu().numpy()


def extract(items: list[Item], tag: str, batch: int = 32) -> dict:
    """Cache handcrafted, DINOv2 and CLIP features for `items` into one .npz per tag."""
    from .features import DinoExtractor, _sync, device

    out = FEATURES / f"{tag}.npz"
    if out.exists():
        z = np.load(out, allow_pickle=False)
        if list(z["names"]) == [i.name for i in items]:
            return json.loads((FEATURES / f"{tag}.timing.json").read_text())
    FEATURES.mkdir(parents=True, exist_ok=True)
    dev = device()
    dino, clip = DinoExtractor(dev), Clip(dev)
    hand, emb, zs = [], [], []
    t = {"decode_s": 0.0, "handcrafted_s": 0.0, "dino_s": 0.0, "clip_s": 0.0}
    for i in range(0, len(items), batch):
        chunk = items[i : i + batch]
        t0 = time.perf_counter()
        imgs = [load_rgb(it.path) for it in chunk]
        small = [load_rgb(it.path, 360) for it in chunk]
        t1 = time.perf_counter()
        hand += [handcrafted(x) for x in small]
        t2 = time.perf_counter()
        for x in imgs:  # sizes differ across cameras; one image per forward pass keeps it exact
            emb.append(dino.embed(x[None])[0])
        _sync(dev)
        t3 = time.perf_counter()
        zs.append(clip.fog_prob(imgs))
        _sync(dev)
        t4 = time.perf_counter()
        for k, a, b in (("decode_s", t0, t1), ("handcrafted_s", t1, t2), ("dino_s", t2, t3), ("clip_s", t3, t4)):
            t[k] += b - a
        if (i // batch) % 20 == 0:
            print(f"{tag}: {i + len(chunk)}/{len(items)}", flush=True)
    np.savez(out, names=np.array([it.name for it in items]), hand=np.stack(hand), dino=np.stack(emb),
             clip=np.concatenate(zs))
    timing = {k: 1000 * v / len(items) for k, v in t.items()} | {"images": len(items), "device": dev.type}
    timing = {k.replace("_s", "_ms_per_image") if k.endswith("_s") else k: v for k, v in timing.items()}
    (FEATURES / f"{tag}.timing.json").write_text(json.dumps(timing, indent=2))
    return timing


def load(tag: str) -> dict[str, np.ndarray]:
    z = np.load(FEATURES / f"{tag}.npz", allow_pickle=False)
    return {k: z[k] for k in z.files}


def center_by_camera(x: np.ndarray, cameras: list[str]) -> np.ndarray:
    """Subtract each camera's mean feature (unlabelled; the camera's own history in deployment)."""
    cams = np.array(cameras)
    out = x.copy()
    for c in np.unique(cams):
        m = cams == c
        out[m] -= x[m].mean(0)
    return out


def fit_lr(x: np.ndarray, y: np.ndarray, c: float):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=c, class_weight="balanced", max_iter=5000)).fit(x, y)


def max_f1_threshold(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import precision_recall_curve

    p, r, t = precision_recall_curve(y, s)
    f1 = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-12)
    return float(t[int(np.argmax(f1))])


def scores_at(y: np.ndarray, s: np.ndarray, thr: float) -> dict:
    pred = s >= thr
    tp, fp, fn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    neg = int((y == 0).sum())
    return {"threshold": thr, "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec,
            "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0, "fpr": fp / neg if neg else None}


def ranking(y: np.ndarray, s: np.ndarray) -> dict:
    from sklearn.metrics import average_precision_score, roc_auc_score

    if len(set(y.tolist())) < 2:
        return {"auroc": None, "auprc": None, "n": int(len(y)), "positives": int(y.sum())}
    return {"auroc": float(roc_auc_score(y, s)), "auprc": float(average_precision_score(y, s)),
            "n": int(len(y)), "positives": int(y.sum())}


def camera_bootstrap_diff(y, a, b, cameras, n=2000, seed=0) -> dict:
    """AUPRC(a) - AUPRC(b), resampling cameras with replacement."""
    from sklearn.metrics import average_precision_score

    cams = np.array(cameras)
    uniq = np.unique(cams)
    idx = {c: np.flatnonzero(cams == c) for c in uniq}
    rng, diffs = np.random.default_rng(seed), []
    for _ in range(n):
        sel = np.concatenate([idx[c] for c in rng.choice(uniq, len(uniq))])
        if len(set(y[sel].tolist())) < 2:
            continue
        diffs.append(average_precision_score(y[sel], a[sel]) - average_precision_score(y[sel], b[sel]))
    d = np.array(diffs)
    return {"mean": float(d.mean()), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
            "resamples": int(len(d))}
