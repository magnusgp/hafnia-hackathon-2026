"""Offline camera-view comparison. Produces a review gate, never polygon approval.

Run on the existing Linux CV environment. Dynamic/occluded/ambiguous views fail
closed. These conservative thresholds are calibration policy, not accuracy claims.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(reference, current):
    import cv2
    import numpy as np
    a = cv2.imread(str(reference), cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(str(current), cv2.IMREAD_GRAYSCALE)
    if a is None or b is None or a.shape != b.shape:
        return dict(state='reapproval_required', reason='Image dimensions changed or image unavailable')
    height, width = a.shape
    detector = cv2.ORB_create(nfeatures=3000)
    ka, da = detector.detectAndCompute(a, None)
    kb, db = detector.detectAndCompute(b, None)
    if da is None or db is None:
        return dict(state='reapproval_required', reason='Insufficient static view features')
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < .65 * pair[1].distance]
    if len(good) < 30:
        return dict(state='reapproval_required', reason='Insufficient matching view features')
    source = np.float32([ka[m.queryIdx].pt for m in good])
    target = np.float32([kb[m.trainIdx].pt for m in good])
    transform, mask = cv2.findHomography(source, target, cv2.RANSAC, 2.0)
    if transform is None or mask is None:
        return dict(state='reapproval_required', reason='Camera view comparison is inconclusive')
    inliers = mask.ravel().astype(bool)
    count, ratio = int(inliers.sum()), float(inliers.mean())
    quadrants = [0, 0, 0, 0]
    for x, y in source[inliers]:
        quadrants[int(x >= width / 2) + 2 * int(y >= height / 2)] += 1
    corners = np.float32([[0,0],[width,0],[width,height],[0,height]]).reshape(1,4,2)
    projected = cv2.perspectiveTransform(corners, transform)[0]
    displacement = float(np.max(np.abs((projected - corners[0]) / np.array([width,height]))))
    matches = count >= 30 and ratio >= .6 and min(quadrants) >= 3 and np.isfinite(displacement) and displacement <= .005
    return dict(state='view_matches' if matches else 'reapproval_required',
                dimensions=[width,height], inliers=count, inlier_ratio=ratio,
                quadrant_inliers=quadrants, max_corner_displacement=displacement if np.isfinite(displacement) else None)


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--spatial',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    spatial = json.loads(a.spatial.read_text(encoding='utf-8-sig'))
    manifest = json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    if spatial['camera_guid'].lower() != manifest['camera_id'].lower() or sha(a.reference) != spatial['reference_frame_sha256']:
        raise ValueError('Camera-specific reference identity mismatch')
    checks = []
    for frame in manifest['frames']:
        path = (a.manifest.parent / frame['file']).resolve()
        if not path.is_relative_to(a.manifest.parent.resolve()) or sha(path) != frame['sha256']:
            raise ValueError('Current frame identity mismatch')
        checks.append(dict(frame_sha256=frame['sha256'], **compare(a.reference, path)))
    if not checks:
        raise ValueError('No current frames')
    report = dict(camera_guid=manifest['camera_id'].lower(), manifest_sha256=sha(a.manifest),
                  reference_frame_sha256=sha(a.reference), runner_sha256=sha(__file__),
                  policy='orb-static-view-v1', checks=checks,
                  state='view_matches' if all(c['state']=='view_matches' for c in checks) else 'reapproval_required')
    a.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report['state'])


if __name__ == '__main__':
    main()
