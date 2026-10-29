"""Window choice for cameras that replay a short clip (the hackathon cameras do), without a reference clip.

A restart shows up as one isolated jump between consecutive frames of the exported video (10 frames per second). Two or
more jumps with a steady gap give the period and the restart instant. The result only picks a window that sits inside one
cycle; every window is still checked again after it is recorded, so a wrong estimate fails visibly instead of reaching
Hafnia. A visually seamless loop shows no jump: such a camera needs a reference clip (Watch setting `source.loopReference`).
"""
from datetime import timedelta, timezone
import json
from pathlib import Path
import shutil
import statistics

from adaptive_watch.assessment_job import choose_interval, iso, parse

MAX_AGE_S = 6*3600
MEASURE_S = 45


def find_jumps(diffs, ratio=5.0, floor=3.0, span=5):
    """Indices i where the step from frame i to i+1 is an isolated jump (far above the floor and its neighbours)."""
    hits = []
    for i, value in enumerate(diffs):
        near = diffs[max(0, i-span):i]+diffs[i+1:i+1+span]
        if near and value > floor and value/max(statistics.median(near), .5) > ratio:
            hits.append(i)
    return hits


def estimate(times, diffs, ratio=5.0, floor=3.0):
    """(seam_times, period) from frame times and consecutive differences.

    The period is None unless at least two jumps were seen with one steady gap (so a single content cut, or a clip with two
    cuts per cycle, is not mistaken for a loop).
    """
    seams = [times[i+1] for i in find_jumps(diffs, ratio, floor)]
    if len(seams) < 2:
        return seams, None
    gaps = [b-a for a, b in zip(seams, seams[1:])]
    period = round(statistics.median(gaps))
    return seams, period if period >= 5 and all(abs(g-period) <= 0.35 for g in gaps) else None


def seam_utc(first_snapshot_utc, seam_media_time, export_offset):
    """UTC instant of a restart seen at `seam_media_time` seconds into the export (snapshot 0 sits at `export_offset`)."""
    t = parse(first_snapshot_utc)+timedelta(seconds=seam_media_time-export_offset)
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'  # milliseconds: windows are cut tight to the restart


def measure(effects, camera, sequences, now, scratch):
    """Returns dict(periodic=False, ...) or dict(periodic=True, seam_utc, period). Reads the recording only."""
    scratch = Path(scratch)
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        start, end = choose_interval(sequences, now, window=MEASURE_S, margin=100, hafnia=False)
    except ValueError:
        return dict(periodic=False, reason='No long enough retained recording to measure the camera loop')
    try:
        manifest = effects.acquire(camera, start, end, scratch/'acq', interval='0.5', mkv=True)
        try:
            info, diffs = effects.encode(manifest, scratch/'media')
        except ValueError as exc:
            return dict(periodic=False, reason=f'The recording could not be aligned for loop measurement: {exc}', measured_window=[start, end])
        times = [i/info['fps'] for i in range(len(diffs)+1)]
        seams, period = estimate(times, diffs)
        if period is None:
            return dict(periodic=False, seams=len(seams), measured_window=[start, end])
        first = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))['frames'][0]['timestamp_utc']
        return dict(periodic=True, seam_utc=seam_utc(first, seams[0], info.get('exportOffset', -0.1)), period=period, measured_window=[start, end])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def window_phase(effects, cfg, sequences, now, root):
    """Cached loop phase for the Watch's camera: {'seam_utc','period'} or None when no loop was found."""
    path = Path(root)/'loops'/(cfg['camera']['id'].lower()+'.json')
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        if (now-parse(saved['measured_at'])).total_seconds() < MAX_AGE_S:
            return dict(seam_utc=saved['seam_utc'], period=saved['period']) if saved.get('periodic') else None
    result = measure(effects, cfg['camera']['name'], sequences, now, Path(root)/'loops'/('.scratch-'+cfg['camera']['id'].lower()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(result, measured_at=now.isoformat()), indent=2), encoding='utf-8')
    return dict(seam_utc=result['seam_utc'], period=result['period']) if result.get('periodic') else None
