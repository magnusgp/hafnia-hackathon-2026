import importlib.util
import unittest
from pathlib import Path

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


@unittest.skipUnless(HAVE_ML, "requires `uv sync --group ml`")
class FootageTest(unittest.TestCase):
    def _manifest(self, d, stamps, **extra):
        import json

        import numpy as np
        from PIL import Image

        frames = []
        for i, t in enumerate(stamps):
            Image.fromarray(np.full((36, 64, 3), i * 10, dtype=np.uint8)).save(f"{d}/f{i}.jpg")
            frames.append({"file": f"f{i}.jpg", "timestamp_utc": t})
        m = {"source": "Get-Snapshot", "camera_name": "cam", "requested_start_utc": "2026-10-21T12:00:00Z",
             "requested_end_utc": "2026-10-21T12:00:02Z", "frames": frames, **extra}
        (Path(d) / "manifest.json").write_text(json.dumps(m))
        return Path(d) / "manifest.json"

    def test_snapshot_manifest_timestamps_are_reported_exactly(self):
        import tempfile

        from adaptive_watch import footage

        with tempfile.TemporaryDirectory() as d:
            path = self._manifest(d, ["2026-10-21T12:00:00.500Z", "2026-10-21T12:00:01Z", "2026-10-21T12:00:01Z",
                                      "2026-10-21T12:00:03Z"])
            frames, _ = footage.snapshot_frames(path)
            r = footage.timestamp_report([f.timestamp for f in frames], footage.parse_utc("2026-10-21T12:00:00Z"),
                                         footage.parse_utc("2026-10-21T12:00:02Z"))
        self.assertEqual(frames[0].rgb.shape, (36, 64, 3))
        self.assertEqual((r["first_utc"], r["last_utc"]), ("2026-10-21T12:00:00.500000Z", "2026-10-21T12:00:03Z"))
        self.assertEqual((r["duplicate_timestamps"], r["outside_requested_range"]), (1, 1))

    def test_manifest_rejects_unordered_naive_or_escaping_frames(self):
        import tempfile

        from adaptive_watch import footage

        bad = [["2026-10-21T12:00:01Z", "2026-10-21T12:00:00Z"], ["2026-10-21T12:00:00"]]
        for stamps in bad:
            with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
                footage.load_manifest(self._manifest(d, stamps))
        with tempfile.TemporaryDirectory() as d:
            path = self._manifest(d, ["2026-10-21T12:00:00Z"])
            m = path.read_text().replace('"f0.jpg"', '"../f0.jpg"')
            path.write_text(m)
            with self.assertRaises(ValueError):
                footage.load_manifest(path)

    def test_mkv_sampling_keeps_a_fixed_grid(self):
        import tempfile
        from datetime import timezone

        import av
        import numpy as np

        from adaptive_watch import footage

        with tempfile.TemporaryDirectory() as d:
            with av.open(f"{d}/c.mkv", "w") as c:
                s = c.add_stream("mpeg4", rate=25)
                s.width, s.height, s.pix_fmt = 64, 48, "yuv420p"
                for i in range(100):
                    frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), i, dtype=np.uint8), format="rgb24")
                    for pkt in s.encode(frame):
                        c.mux(pkt)
                for pkt in s.encode():
                    c.mux(pkt)
            start = footage.parse_utc("2026-10-21T12:00:00Z")
            frames, meta = footage.mkv_frames(Path(d) / "c.mkv", start, 2.0)
        self.assertEqual(meta["decoded_frames"], 100)
        rel = [(f.timestamp - start).total_seconds() for f in frames]
        self.assertEqual(len(rel), 8)
        self.assertTrue(all(abs(r - 0.5 * i) < 0.021 for i, r in enumerate(rel)), rel)
        self.assertEqual(frames[0].timestamp.tzinfo, timezone.utc)

    def test_capacity_arithmetic(self):
        from adaptive_watch.footage import capacity

        c = capacity(50.0)
        self.assertAlmostEqual(c["frames_per_s"], 20.0)
        self.assertEqual(c["cameras_at_fps"]["2.0"], 10.0)


if __name__ == "__main__":
    unittest.main()
