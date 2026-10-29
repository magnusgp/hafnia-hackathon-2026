"""Window choice for cameras that replay a short clip (the hackathon cameras do), without a reference clip.

A restart shows up as one isolated jump between consecutive frames. Two coarse jumps give the period; a dense look around
one gives the restart instant to 0.1 s. The result is only used to pick a window that sits inside one cycle; every window
is still checked again after it is recorded, so a wrong estimate fails visibly instead of reaching Hafnia.
"""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import shutil
import statistics
import sys

from adaptive_watch.assessment_job import choose_interval, iso, parse

MAX_AGE_S = 6*3600
COARSE_S, FINE_S = 34, 3


def find_jumps(diffs, ratio=6.0, floor=4.0, span=5):
    """Indices i where the step from frame i to i+1 is an isolated jump (far above the floor and its neighbours)."""
    hits = []
    for i, value in enumerate(diffs):
        near = diffs[max(0, i-span):i]+diffs[i+1:i+1+span]
        if near and value > floor and value/max(statistics.median(near), .5) > ratio:
            hits.append(i)
    return hits


def estimate(times, diffs):
    """(seam_times, period) from frame times and consecutive differences; period is None unless two restarts were seen."""
    seams = [times[i+1] for i in find_jumps(diffs)]
    if len(seams) < 2:
        return seams, None
    gaps = [b-a for a, b in zip(seams, seams[1:])]
    period = round(statistics.median(gaps))
    return seams, period if period >= 5 and all(abs(g-period) <= 1.0 for g in gaps) else None


def _gray_diffs(manifest, deps=None):
    if deps:
        sys.path.insert(0, str(Path(deps).resolve()))
    import numpy as np
    from PIL import Image
    m = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    frames, times = [], []
    for f in m['frames']:
        with Image.open(Path(manifest).parent/f['file']) as im:
            frames.append(np.asarray(im.convert('L').resize((104, 60)), dtype=float))
        times.append(parse(f['timestamp_utc']).timestamp())
    return times, [float(np.abs(b-a).mean()) for a, b in zip(frames, frames[1:])]


def measure(effects, camera, sequences, now, scratch):
    """Returns dict(periodic=False) or dict(periodic=True, seam_utc, period). Reads the recording only."""
    scratch = Path(scratch)
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        start, end = choose_interval(sequences, now, window=COARSE_S, margin=100)
    except ValueError:
        return dict(periodic=False, reason='No long enough retained recording to measure the camera loop')
    try:
        coarse = effects.acquire(camera, start, end, scratch/'coarse', interval='0.5', mkv=False)
        times, diffs = _gray_diffs(coarse, effects.deps)
        seams, period = estimate(times, diffs)
        if period is None:
            return dict(periodic=False, seams=len(seams), measured_window=[start, end])
        first = seams[0]
        a = datetime.fromtimestamp(math.floor(first-FINE_S/2), timezone.utc)
        fine = effects.acquire(camera, iso(a), iso(a+timedelta(seconds=FINE_S)), scratch/'fine', interval='0.1', mkv=False)
        ft, fd = _gray_diffs(fine, effects.deps)
        jumps = find_jumps(fd, ratio=4.0, floor=3.0)
        if len(jumps) != 1:
            return dict(periodic=False, seams=len(seams), reason='Could not locate the restart instant precisely', measured_window=[start, end])
        seam = datetime.fromtimestamp(ft[jumps[0]+1], timezone.utc)
        return dict(periodic=True, seam_utc=iso(seam), period=period, measured_window=[start, end])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def window_phase(effects, cfg, sequences, now, root):
    """Cached loop phase for the Watch's camera: {'seam_utc','period'} or None when the camera does not loop."""
    path = Path(root)/'loops'/(cfg['camera']['id'].lower()+'.json')
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        if (now-parse(saved['measured_at'])).total_seconds() < MAX_AGE_S:
            return dict(seam_utc=saved['seam_utc'], period=saved['period']) if saved.get('periodic') else None
    result = measure(effects, cfg['camera']['name'], sequences, now, Path(root)/'loops'/('.scratch-'+cfg['camera']['id'].lower()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(result, measured_at=now.isoformat()), indent=2), encoding='utf-8')
    return dict(seam_utc=result['seam_utc'], period=result['period']) if result.get('periodic') else None
