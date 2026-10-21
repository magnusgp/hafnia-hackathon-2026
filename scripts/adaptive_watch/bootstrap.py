"""Post-hoc (not pre-registered): clip-level bootstrap of event-recall difference vs periodic.

    uv run --group ml python scripts/adaptive_watch/bootstrap.py avenue
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import aw  # noqa: E402
from adaptive_watch import datasets, features, metrics, novelty  # noqa: E402

ds = sys.argv[1]
split = datasets.SPLITS[ds]
cfg = json.loads((aw.RESULTS / ds / "config.json").read_text())
names = split.test_normal + split.test
seqs = {s.name: s for s in datasets.sequences(ds, names)}
memory = novelty.PatchMemory([features.load(ds, n)[0] for n in split.memory])
sig, _, _ = aw._signals(ds, names, memory)
scores = aw._method_scores(cfg, sig)
win_len, fps = datasets.WINDOW[ds], seqs[names[0]].fps
rng = np.random.default_rng(0)
out = {}
for method in ("dino", "motion", "fused"):
    per = {}
    for n in names:
        lab = seqs[n].labels if seqs[n].labels is not None else np.zeros(len(scores[method][n]), dtype=bool)
        per[n] = (metrics.windows(n, scores[method][n], lab, win_len), metrics.events(n, lab, win_len))
    out[method] = {}
    for b in (0.05, 0.10, 0.20, 0.30):
        diffs = []
        for _ in range(2000):
            pick = rng.choice(names, len(names), replace=True)
            wins, evts = [], []
            for j, n in enumerate(pick):  # rename duplicates so they count as separate clips
                wins += [metrics.Window(f"{n}#{j}", w.start, w.end, w.score, w.anomalous) for w in per[n][0]]
                evts += [metrics.Event(f"{n}#{j}", e.start, e.end) for e in per[n][1]]
            if not evts:
                continue
            model = metrics.selection_stats(evts, wins, metrics.top_budget(wins, b), fps)["event_recall"]
            step = max(1, round(1 / b))
            per_phase = [metrics.selection_stats(evts, wins, metrics.periodic(wins, b, p), fps)["event_recall"] for p in range(step)]
            diffs.append(model - float(np.mean(per_phase)))
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        out[method][f"{b:.2f}"] = {"mean_diff": float(np.mean(diffs)), "ci95": [float(lo), float(hi)],
                                   "p_le_0": float(np.mean(np.array(diffs) <= 0))}
        print(method, b, out[method][f"{b:.2f}"])
(aw.RESULTS / ds / "bootstrap_posthoc.json").write_text(json.dumps(out, indent=2) + "\n")
