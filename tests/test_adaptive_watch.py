import importlib.util
import unittest

HAVE_ML = all(importlib.util.find_spec(m) for m in ("numpy", "sklearn", "torch"))


@unittest.skipUnless(HAVE_ML, "requires `uv sync --group ml`")
class MetricsTest(unittest.TestCase):
    def setUp(self):
        import numpy as np

        from adaptive_watch import metrics

        self.np, self.m = np, metrics

    def test_events_merge_short_gaps(self):
        labels = self.np.array([0, 1, 1, 0, 1, 0, 0, 0, 1, 1], dtype=bool)
        self.assertEqual([(e.start, e.end) for e in self.m.events("s", labels)], [(1, 3), (4, 5), (8, 10)])
        self.assertEqual([(e.start, e.end) for e in self.m.events("s", labels, 2)], [(1, 5), (8, 10)])

    def test_windows_use_max_score_and_any_label(self):
        scores = self.np.array([0.1, 0.9, 0.2, 0.3, 0.4])
        labels = self.np.array([0, 0, 0, 1, 0], dtype=bool)
        w = self.m.windows("s", scores, labels, 2)
        self.assertEqual([(x.start, x.end, x.score, x.anomalous) for x in w],
                         [(0, 2, 0.9, False), (2, 4, 0.3, True), (4, 5, 0.4, False)])

    def test_budget_selection_and_periodic_baseline(self):
        np = self.np
        labels = np.zeros(100, dtype=bool)
        labels[40:45] = True  # one short event inside window 4
        scores = np.zeros(100)
        scores[42] = 1.0
        wins = self.m.windows("s", scores, labels, 10)
        evts = self.m.events("s", labels)
        top = self.m.selection_stats(evts, wins, self.m.top_budget(wins, 0.1), fps=10)
        self.assertEqual((top["selected"], top["event_recall"], top["false_windows"]), (1, 1.0, 0))
        hits = [self.m.selection_stats(evts, wins, self.m.periodic(wins, 0.1, p), 10)["event_recall"] for p in range(10)]
        self.assertAlmostEqual(sum(hits) / 10, 0.1)  # periodic hits a one-window event with p = budget

    def test_operating_point_counts_false_alerts_per_normal_hour(self):
        np = self.np
        labels = np.zeros(20, dtype=bool)
        scores = np.zeros(20)
        scores[3] = 5.0
        wins = self.m.windows("s", scores, labels, 10)
        op = self.m.threshold_stats([], wins, 1.0, fps=10)
        self.assertEqual(op["false_windows"], 1)
        self.assertAlmostEqual(op["false_alerts_per_normal_hour"], 1 / (20 / 10 / 3600))


@unittest.skipUnless(HAVE_ML, "requires `uv sync --group ml`")
class NoveltyTest(unittest.TestCase):
    def test_smoothing_is_causal(self):
        import numpy as np

        from adaptive_watch.novelty import smooth

        s = smooth(np.array([0.0, 0.0, 9.0, 0.0]), 3)
        self.assertEqual(list(s), [0.0, 0.0, 3.0, 3.0])

    def test_memory_matches_only_neighbouring_cells(self):
        import numpy as np
        import torch

        from adaptive_watch.novelty import PatchMemory

        d = 4
        normal = np.zeros((2, 3, 3, d), dtype=np.float16)
        normal[..., 0] = 1.0
        normal[:, 0, 0] = [0, 1, 0, 0]  # a pattern seen only in the top-left cell
        mem = PatchMemory([normal], dev=torch.device("cpu"))
        q = np.zeros((1, 3, 3, d), dtype=np.float16)
        q[..., 0] = 1.0
        q[0, 1, 1] = [0, 1, 0, 0]  # adjacent to top-left: familiar
        q[0, 2, 2] = [0, 1, 0, 0]  # two cells away: novel
        s = mem.patch_scores(q)[0]
        self.assertAlmostEqual(float(s[1, 1]), 0.0, places=3)
        self.assertAlmostEqual(float(s[2, 2]), 1.0, places=3)
        self.assertAlmostEqual(float(s[0, 1]), 0.0, places=3)


if __name__ == "__main__":
    unittest.main()
