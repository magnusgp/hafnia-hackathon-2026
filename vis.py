"""Visibility-degradation experiment CLI (pre-registered: docs/research/visibility/preregistration.md).

    uv run --group ml python vis.py extract            # cache features (TA)
    uv run --group ml python vis.py select             # fit/val only -> results/visibility/config.json
    git add results/visibility/config.json && git commit   # lock before the test
    uv run --group ml python vis.py test               # once, frozen config
    uv run --group ml python vis.py external           # once, Digitraffic, frozen model + threshold
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from adaptive_watch import visibility as v

ROOT = Path(__file__).parent
OUT = ROOT / "results" / "visibility"
C_GRID = (0.01, 0.1, 1.0, 10.0)


def committed(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], capture_output=True).returncode == 0
    return tracked and subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel]).returncode == 0


def arrays(items, feats, names_index):
    keep = [i for i in items if i.label is not None]
    rows = np.array([names_index[i.name] for i in keep])
    return keep, np.array([i.label for i in keep]), {k: feats[k][rows] for k in ("hand", "dino", "clip")}


def centered_dino(items, feats, names_index):
    """Per-camera centering over ALL of a split's images of that camera (labels unused)."""
    rows = np.array([names_index[i.name] for i in items])
    return v.center_by_camera(feats["dino"][rows], [i.camera for i in items]), {i.name: k for k, i in enumerate(items)}


def method_scores(method: str, c: float | None, fit, val_or_test) -> np.ndarray:
    """fit / target: (labelled items, y, feature dict, centred-dino rows)."""
    _, y_fit, f_fit, cen_fit = fit
    _, _, f_t, cen_t = val_or_test
    if method in v.BASELINES:
        return f_t["hand"][:, v.HANDCRAFTED.index(v.BASELINES[method])]
    if method == "P1":
        return f_t["clip"]
    x_fit, x_t = {"B4": (f_fit["hand"], f_t["hand"]), "M1": (f_fit["dino"], f_t["dino"]),
                  "M2": (cen_fit, cen_t)}[method]
    return v.fit_lr(x_fit, y_fit, c).predict_proba(x_t)[:, 1]


def prepare(items, feats):
    idx = {n: k for k, n in enumerate(feats["names"])}
    keep, y, f = arrays(items, feats, idx)
    cen, cen_idx = centered_dino(items, feats, idx)
    return keep, y, f, cen[[cen_idx[i.name] for i in keep]]


def all_ta():
    splits = v.ta_items()
    items = splits["fit"] + splits["val"] + splits["test"]
    return splits, items


def cmd_extract(_):
    _, items = all_ta()
    print(json.dumps(v.extract(items, "ta"), indent=2))


def cmd_select(_):
    splits, _ = all_ta()
    feats = v.load("ta")
    fit, val = prepare(splits["fit"], feats), prepare(splits["val"], feats)
    y = val[1]
    grid = {}
    for m in ("B1", "B2", "B3", "P1"):
        grid[m] = v.ranking(y, method_scores(m, None, fit, val))
    for m in ("B4", "M1", "M2"):
        for c in C_GRID:
            grid[f"{m}/C={c}"] = v.ranking(y, method_scores(m, c, fit, val))
    learned = max((k for k in grid if k.startswith(("M1", "M2"))), key=lambda k: grid[k]["auprc"])
    baseline = max((k for k in grid if not k.startswith(("M1", "M2"))), key=lambda k: grid[k]["auprc"])

    def parse(k):
        m, _, c = k.partition("/C=")
        return {"method": m, "C": float(c) if c else None}

    cfg = {"learned": parse(learned), "baseline": parse(baseline), "label_thresholds": {"pos": v.POS, "neg": v.NEG}}
    for role in ("learned", "baseline"):
        s = method_scores(cfg[role]["method"], cfg[role]["C"], fit, val)
        cfg[role]["threshold"] = v.max_f1_threshold(y, s)
        cfg[role]["val"] = {**grid[learned if role == "learned" else baseline],
                            **v.scores_at(y, s, cfg[role]["threshold"])}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    counts = {s: {"images": len(splits[s]), "cameras": len({i.camera for i in splits[s]}),
                  "positive": sum(i.label == 1 for i in splits[s]), "negative": sum(i.label == 0 for i in splits[s]),
                  "excluded": sum(i.label is None for i in splits[s])} for s in splits}
    (OUT / "val.json").write_text(json.dumps({"counts": counts, "grid_val": grid, "config": cfg}, indent=2) + "\n")
    print(json.dumps({"counts": counts, "selected": cfg}, indent=2))
    print("\n| candidate | val AUROC | val AUPRC |\n|---|---|---|")
    for k, r in grid.items():
        print(f"| {k} | {r['auroc']:.3f} | {r['auprc']:.3f} |")


def evaluate(target_items, cfg, tag_feats, fit):
    tgt = prepare(target_items, tag_feats)
    keep, y = tgt[0], tgt[1]
    cams = [i.camera for i in keep]
    out = {"n": len(y), "positives": int(y.sum()), "cameras": len(set(cams)),
           "positive_cameras": len({c for c, l in zip(cams, y) if l == 1})}
    s = {}
    for role in ("learned", "baseline"):
        s[role] = method_scores(cfg[role]["method"], cfg[role]["C"], fit, tgt)
        out[role] = {"method": cfg[role], **v.ranking(y, s[role]), **v.scores_at(y, s[role], cfg[role]["threshold"])}
    out["all_methods"] = {m: v.ranking(y, method_scores(m, c, fit, tgt)) for m, c in
                          (("B1", None), ("B2", None), ("B3", None), ("P1", None), ("B4", cfg["baseline"]["C"] or 1.0),
                           ("M1", cfg["learned"]["C"]), ("M2", cfg["learned"]["C"]))}
    out["auprc_diff_camera_bootstrap"] = v.camera_bootstrap_diff(y, s["learned"], s["baseline"], cams)
    per_cam = {}
    for c in sorted(set(cams)):
        m = np.array(cams) == c
        per_cam[c] = {**v.ranking(y[m], s["learned"][m])}
    out["per_camera_learned"] = per_cam
    order = np.argsort(-s["learned"])
    thr = cfg["learned"]["threshold"]
    out["failures"] = {
        "top_false_positives": [{"name": keep[k].name, "score": float(s["learned"][k]), **keep[k].attrs}
                                for k in order if y[k] == 0][:8],
        "lowest_false_negatives": [{"name": keep[k].name, "score": float(s["learned"][k]), **keep[k].attrs}
                                   for k in order[::-1] if y[k] == 1 and s["learned"][k] < thr][:8],
    }
    return out, keep, y, s


def gate(res, min_diff=0.05):
    d = res["learned"]["auprc"] - res["baseline"]["auprc"]
    lo = res["auprc_diff_camera_bootstrap"]["ci95"][0]
    return {"auprc_diff": d, "ci95_lower": lo, "pass": bool(d >= min_diff and lo > 0)}


def cmd_test(args):
    cfg_path = OUT / "config.json"
    if not committed(cfg_path):
        sys.exit(f"{cfg_path} must be committed (and unmodified) before the final test.")
    if (OUT / "test.json").exists() and not args.rerun:
        sys.exit("test.json exists; the final test is run once.")
    cfg = json.loads(cfg_path.read_text())
    splits, _ = all_ta()
    feats = v.load("ta")
    res, keep, y, s = evaluate(splits["test"], cfg, feats, prepare(splits["fit"], feats))
    # Secondary: does the fog score fire on clear-but-night/rain/snow images?
    thr = cfg["learned"]["threshold"]
    res["secondary_fpr_at_threshold"] = {}
    for a in v.SECONDARY:
        m = np.array([y[k] == 0 and keep[k].attrs[a] >= v.POS for k in range(len(keep))])
        res["secondary_fpr_at_threshold"][a] = {"clear_images_with_attr": int(m.sum()),
                                                "fpr": float((s["learned"][m] >= thr).mean()) if m.any() else None}
    res["gate"] = gate(res)
    res["config_commit"] = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(cfg_path)],
                                          capture_output=True, text=True).stdout.strip()
    res["latency"] = json.loads((v.FEATURES / "ta.timing.json").read_text())
    (OUT / "test.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps({k: res[k] for k in ("n", "positives", "cameras", "learned", "baseline", "gate",
                                           "auprc_diff_camera_bootstrap", "secondary_fpr_at_threshold")}, indent=2))


def solar_elevation(lon: float, lat: float, when: datetime) -> float:
    """Approximate solar elevation (degrees), NOAA low-precision formula; enough for day/night."""
    d = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60
    g = 2 * math.pi / 365 * (d - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                    - 0.040849 * math.sin(2 * g))
    ha = math.radians(((hour * 60 + eqt + 4 * lon) / 4) - 180)
    la = math.radians(lat)
    return math.degrees(math.asin(math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)))


def cmd_external(args):
    from adaptive_watch import digitraffic

    cfg_path = OUT / "config.json"
    if not committed(cfg_path) or not (OUT / "test.json").exists():
        sys.exit("External test runs only after the committed config and the TA final test.")
    if (OUT / "external.json").exists() and not args.rerun:
        sys.exit("external.json exists; the external test is run once.")
    items = v.dt_items()
    pos = [i for i in items if i.label == 1]
    pos_cams = {i.camera for i in pos}
    deadline = datetime.fromisoformat("2026-10-29T12:00:00+01:00")
    ready = len(pos) >= 50 and len(pos_cams) >= 8
    if not ready and datetime.now().astimezone() < deadline and not args.force_early:
        sys.exit(f"Not ready: {len(pos)} positives from {len(pos_cams)} cameras (need 50 / 8, or the deadline).")
    if len(pos) < 20 or len(pos_cams) < 5:
        res = {"status": "insufficient external data", "positives": len(pos), "positive_cameras": len(pos_cams)}
        (OUT / "external.json").write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps(res, indent=2))
        return
    print(json.dumps(v.extract(items, "dt"), indent=2))
    cfg = json.loads(cfg_path.read_text())
    splits, _ = all_ta()
    ta = v.load("ta")
    dt = v.load("dt")
    fit = prepare(splits["fit"], ta)
    res, keep, y, s = evaluate(items, cfg, dt, fit)
    cams = {c["camera"]: c for c in digitraffic.camera_set()}
    day = np.array([solar_elevation(*cams[i.camera]["lon_lat"], datetime.fromisoformat(i.attrs["captured"])) > 0
                    for i in keep])
    thr = cfg["learned"]["threshold"]
    res["by_daylight"] = {name: {**v.ranking(y[m], s["learned"][m]), **v.scores_at(y[m], s["learned"][m], thr)}
                          for name, m in (("day", day), ("night", ~day))}
    fpr = res["learned"]["fpr"]
    res["false_alerts_per_camera_day"] = None if fpr is None else fpr * 144
    res["external_gate"] = {"pass": bool(res["learned"]["auroc"] >= 0.80 and
                                         res["learned"]["auroc"] > res["baseline"]["auroc"])}
    res["status"] = "evaluated" if ready else "evaluated at deadline"
    (OUT / "external.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps({k: res[k] for k in ("status", "n", "positives", "cameras", "positive_cameras", "learned",
                                           "baseline", "by_daylight", "external_gate")}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extract")
    sub.add_parser("select")
    t = sub.add_parser("test")
    t.add_argument("--rerun", action="store_true")
    e = sub.add_parser("external")
    e.add_argument("--rerun", action="store_true")
    e.add_argument("--force-early", action="store_true", help="evaluate before 50/8 or the deadline (documented)")
    a = p.parse_args()
    {"extract": cmd_extract, "select": cmd_select, "test": cmd_test, "external": cmd_external}[a.cmd](a)


if __name__ == "__main__":
    main()
