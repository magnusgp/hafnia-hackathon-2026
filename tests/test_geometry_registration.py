"""Camera-specific reusable approval gates; generated reports are test fixtures."""
import json
from pathlib import Path
import tempfile
import unittest

from adaptive_watch.incident import assemble, sha
import test_sidewalk_incident


class GeometryRegistrationTests(unittest.TestCase):
    def test_reuse_requires_bound_view_check_and_rejects_changed_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = test_sidewalk_incident.IncidentTests().fixture(root)
            spatial = json.loads(args[3].read_text())
            spatial['reference_frame_sha256'] = 'a' * 64  # earlier approved recording
            args[3].write_text(json.dumps(spatial))
            with self.assertRaisesRegex(ValueError, 'view check or reapproval'):
                assemble(*args)
            manifest = json.loads(args[1].read_text())
            report = dict(policy='orb-static-view-v1', runner_sha256=sha(Path(__file__).resolve().parents[1] / 'scripts/adaptive_watch/check_calibration.py'),
                          camera_guid=spatial['camera_guid'], reference_frame_sha256=spatial['reference_frame_sha256'],
                          manifest_sha256=sha(args[1]), state='view_matches',
                          checks=[dict(frame_sha256=f['sha256'], state='view_matches', inliers=40, inlier_ratio=.8,
                                       quadrant_inliers=[10,10,10,10], max_corner_displacement=.001) for f in manifest['frames']])
            path = root / 'geometry.json'
            path.write_text(json.dumps(report))
            self.assertTrue(assemble(*args, path)['dispatch_review_ready'])
            for key, value in [('camera_guid', 'another-camera'), ('manifest_sha256', 'changed'), ('reference_frame_sha256', 'changed')]:
                bad = dict(report, **{key:value}); path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError, 'provenance changed'):
                    assemble(*args, path)
            for delta in (.04, float('nan')):
                report['checks'][0]['max_corner_displacement'] = delta
                path.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, 'changed or ambiguous'):
                    assemble(*args, path)
            report['checks'][0]['max_corner_displacement'] = .001
            report['checks'][0]['inliers'] = 2
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'changed or ambiguous'):
                assemble(*args, path)
