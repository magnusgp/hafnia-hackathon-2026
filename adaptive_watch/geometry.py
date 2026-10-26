"""Validate recording-specific view checks before reusing a camera polygon."""
import json
import math
from pathlib import Path
from adaptive_watch.incident import sha


def validate_registration(path, spatial, manifest, manifest_path):
    report = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    runner = Path(__file__).resolve().parents[1] / 'scripts/adaptive_watch/check_calibration.py'
    if (report.get('policy') != 'orb-static-view-v1' or report.get('runner_sha256') != sha(runner) or
            report.get('camera_guid') != spatial['camera_guid'].lower() or
            report.get('manifest_sha256') != sha(manifest_path) or
            report.get('reference_frame_sha256') != spatial['reference_frame_sha256']):
        raise ValueError('Camera calibration provenance changed; reapproval required')
    checks = report.get('checks', [])
    if (not checks or [c['frame_sha256'] for c in checks] != [f['sha256'] for f in manifest['frames']] or
            report.get('state') != 'view_matches'):
        raise ValueError('Camera calibration changed or unverified; reapproval required')
    for check in checks:
        delta = check.get('max_corner_displacement')
        quadrants = check.get('quadrant_inliers', [])
        if (check.get('state') != 'view_matches' or len(quadrants) != 4 or min(quadrants) < 3 or
                check.get('inliers', 0) < 30 or not .6 <= check.get('inlier_ratio', 0) <= 1 or
                type(delta) not in (float, int) or not math.isfinite(delta) or not 0 <= delta <= .005):
            raise ValueError('Camera calibration changed or ambiguous; reapproval required')
    return dict(path=str(Path(path).resolve()), sha256=sha(path), report=report)
