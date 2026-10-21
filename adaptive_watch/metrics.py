"""Frame/window ranking metrics and VLM-budget selection, with equal-budget baselines.

Scores are pooled across all sequences of a split without per-video normalisation
(per-video min-max would use future footage and is not deployable).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

BUDGETS = (0.05, 0.10, 0.20, 0.30, 0.50)


@dataclass(frozen=True)
class Window:
    seq: str
    start: int  # frame index, inclusive
    end: int  # exclusive
    score: float
    anomalous: bool


@dataclass(frozen=True)
class Event:
    seq: str
    start: int
    end: int  # exclusive


def windows(seq: str, scores: np.ndarray, labels: np.ndarray | None, length: int) -> list[Window]:
    """Non-overlapping windows; a window's score is its maximum frame score."""
    out = []
    for s in range(0, len(scores), length):
        e = min(s + length, len(scores))
        out.append(Window(seq, s, e, float(scores[s:e].max()), bool(labels is not None and labels[s:e].any())))
    return out


def events(seq: str, labels: np.ndarray, merge_gap: int = 0) -> list[Event]:
    """Maximal runs of anomalous frames; runs separated by < merge_gap normal frames are one event."""
    padded = np.concatenate([[False], labels, [False]]).astype(np.int8)
    d = np.diff(padded)
    out: list[Event] = []
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
        if out and a - out[-1].end < merge_gap:
            out[-1] = Event(seq, out[-1].start, int(b))
        else:
            out.append(Event(seq, int(a), int(b)))
    return out


def ranking(labels: np.ndarray, scores: np.ndarray) -> dict:
    if labels.all() or not labels.any():
        return {"auroc": None, "auprc": None, "positive_rate": float(labels.mean())}
    return {
        "auroc": float(roc_auc_score(labels, scores)),
        "auprc": float(average_precision_score(labels, scores)),
        "positive_rate": float(labels.mean()),
    }


def _hits(evts: list[Event], selected: list[Window]) -> list[Window | None]:
    """First selected window overlapping each event, or None."""
    by_seq: dict[str, list[Window]] = {}
    for w in selected:
        by_seq.setdefault(w.seq, []).append(w)
    out = []
    for ev in evts:
        cands = [w for w in by_seq.get(ev.seq, []) if w.start < ev.end and w.end > ev.start]
        out.append(min(cands, key=lambda w: w.start) if cands else None)
    return out


def selection_stats(evts: list[Event], wins: list[Window], selected: list[Window], fps: float) -> dict:
    hits = _hits(evts, selected)
    delays = [max(0, h.start - e.start) / fps for e, h in zip(evts, hits) if h is not None]
    false = sum(not w.anomalous for w in selected)
    normal = sum(not w.anomalous for w in wins)
    normal_hours = sum((w.end - w.start) for w in wins if not w.anomalous) / fps / 3600
    return {
        "selected": len(selected),
        "selected_fraction": len(selected) / len(wins),
        "event_recall": sum(h is not None for h in hits) / len(evts) if evts else None,
        "events_hit": sum(h is not None for h in hits),
        "events": len(evts),
        "window_precision": (len(selected) - false) / len(selected) if selected else None,
        "anomalous_window_recall": (len(selected) - false) / max(1, len(wins) - normal),
        "false_windows": false,
        "normal_windows": normal,
        "false_alerts_per_normal_hour": false / normal_hours if normal_hours else None,
        "median_delay_s": float(np.median(delays)) if delays else None,
    }


def top_budget(wins: list[Window], budget: float) -> list[Window]:
    k = int(np.ceil(budget * len(wins)))
    order = sorted(range(len(wins)), key=lambda i: (-wins[i].score, i))
    return [wins[i] for i in order[:k]]


def periodic(wins: list[Window], budget: float, phase: int) -> list[Window]:
    """Every round(1/budget)-th window of each sequence, starting at `phase`."""
    step = max(1, round(1 / budget))
    out, idx = [], {}
    for w in wins:
        i = idx[w.seq] = idx.get(w.seq, -1) + 1
        if i % step == phase:
            out.append(w)
    return out


def _mean_stats(runs: list[dict]) -> dict:
    keys = [k for k in runs[0] if all(r[k] is not None for r in runs)]
    return {k: float(np.mean([r[k] for r in runs])) for k in keys}


def budget_curve(evts: list[Event], wins: list[Window], fps: float, seeds: int = 1000) -> dict:
    """Score-ranked selection vs. periodic (mean over phases) and random (mean over seeds)."""
    rng = np.random.default_rng(0)
    out = {}
    for b in BUDGETS:
        step = max(1, round(1 / b))
        k = int(np.ceil(b * len(wins)))
        out[f"{b:.2f}"] = {
            "model": selection_stats(evts, wins, top_budget(wins, b), fps),
            "periodic": _mean_stats([selection_stats(evts, wins, periodic(wins, b, p), fps) for p in range(step)]),
            "random": _mean_stats([
                selection_stats(evts, wins, [wins[i] for i in rng.choice(len(wins), k, replace=False)], fps)
                for _ in range(seeds)
            ]),
        }
    return out


def threshold_stats(evts: list[Event], wins: list[Window], threshold: float, fps: float) -> dict:
    return {"threshold": threshold, **selection_stats(evts, wins, [w for w in wins if w.score > threshold], fps)}
