import importlib.util
import unittest
from datetime import datetime, timezone

HAVE_ML = all(importlib.util.find_spec(m) for m in ("numpy", "sklearn", "torch", "scipy"))


@unittest.skipUnless(HAVE_ML, "requires `uv sync --group ml`")
class VisibilityTest(unittest.TestCase):
    def test_haze_raises_dark_channel_and_lowers_contrast(self):
        import numpy as np

        from adaptive_watch.visibility import HANDCRAFTED, handcrafted

        rng = np.random.default_rng(0)
        clear = rng.integers(0, 255, (120, 160, 3)).astype(np.float32)
        hazy = (0.3 * clear + 0.7 * 220).astype(np.uint8)  # atmospheric scattering towards bright airlight
        a, b = handcrafted(clear.astype(np.uint8)), handcrafted(hazy)
        for cue in ("dark_channel", "neg_contrast", "neg_log_laplacian"):
            i = HANDCRAFTED.index(cue)
            self.assertGreater(b[i], a[i], cue)

    def test_camera_centering_uses_only_same_camera(self):
        import numpy as np

        from adaptive_watch.visibility import center_by_camera

        x = np.array([[1.0], [3.0], [10.0], [14.0]])
        out = center_by_camera(x, ["a", "a", "b", "b"])
        self.assertEqual(out[:, 0].tolist(), [-1.0, 1.0, -2.0, 2.0])

    def test_threshold_and_operating_point(self):
        import numpy as np

        from adaptive_watch.visibility import max_f1_threshold, scores_at

        y = np.array([0, 0, 1, 1, 0, 1])
        s = np.array([0.1, 0.2, 0.8, 0.9, 0.7, 0.75])
        thr = max_f1_threshold(y, s)
        self.assertAlmostEqual(thr, 0.75)
        r = scores_at(y, s, thr)
        self.assertEqual((r["tp"], r["fp"], r["fn"], r["f1"], r["fpr"]), (3, 0, 0, 1.0, 0.0))

    def test_camera_bootstrap_of_identical_scores_is_zero(self):
        import numpy as np

        from adaptive_watch.visibility import camera_bootstrap_diff

        y = np.array([0, 1] * 10)
        s = np.linspace(0, 1, 20)
        d = camera_bootstrap_diff(y, s, s, [f"c{i // 4}" for i in range(20)], n=50)
        self.assertEqual((d["mean"], d["ci95"]), (0.0, [0.0, 0.0]))


class GeoTest(unittest.TestCase):
    def test_haversine_km(self):
        from adaptive_watch.digitraffic import _km

        self.assertAlmostEqual(_km((24.94, 60.17), (24.94, 61.17)), 111.2, delta=0.5)

    @unittest.skipUnless(HAVE_ML, "requires `uv sync --group ml`")
    def test_solar_elevation_day_and_night_in_helsinki(self):
        import vis

        noon = vis.solar_elevation(24.94, 60.17, datetime(2026, 6, 21, 10, 20, tzinfo=timezone.utc))
        midnight = vis.solar_elevation(24.94, 60.17, datetime(2026, 12, 21, 22, 0, tzinfo=timezone.utc))
        self.assertAlmostEqual(noon, 53.3, delta=1.0)
        self.assertLess(midnight, -30)


if __name__ == "__main__":
    unittest.main()
