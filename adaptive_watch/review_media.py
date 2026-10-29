"""Re-encode an original XProtect MKV as a browser MP4, frame for frame, and verify snapshot alignment.

Importable form of scripts/adaptive_watch/prepare_review_media.py. av, numpy and PIL are imported lazily.
"""
from fractions import Fraction
import json
from pathlib import Path
import sys

from adaptive_watch.negative_review import read, sha


def prepare(manifest, out, deps=None, adaptive=False):
    """Return (media_info, native_frame_diffs). Raises ValueError if any snapshot does not align.

    The saved railway release assumes the export starts 0.1 s before the first snapshot. With `adaptive` the constant offset
    between the snapshot clock and the export is measured from the first snapshot (searching up to 2 s) and every later
    snapshot must still sit within one native frame of that constant offset. Nothing else about the check is relaxed.
    """
    manifest, out = Path(manifest), Path(out)
    if deps:
        sys.path.insert(0, str(Path(deps).resolve()))
    import av
    import numpy as np
    from PIL import Image
    m = read(manifest)
    src = manifest.parent/m['mkv_export']['file']
    if sha(src) != m['mkv_export']['sha256']:
        raise ValueError('Original MKV hash mismatch')
    out.mkdir(parents=True, exist_ok=True)
    target = out/'original.mp4'
    small, frames = [], []
    with av.open(str(src)) as inp, av.open(str(target), 'w') as out_c:
        s = inp.streams.video[0]
        o = out_c.add_stream('libx264', rate=10)
        o.width, o.height, o.pix_fmt = s.width, s.height, 'yuv420p'
        o.options = dict(crf='16', preset='slow', movflags='faststart')
        first = None
        for f in inp.decode(video=0):
            t = float(f.pts*s.time_base)
            first = t if first is None else first
            frames.append(t)
            small.append(np.asarray(f.to_image().convert('L').resize((104, 60)), dtype=float))
            nf = av.VideoFrame.from_image(f.to_image())
            nf.pts, nf.time_base = round((t-first)*10), Fraction(1, 10)
            for pk in o.encode(nf):
                out_c.mux(pk)
        for pk in o.encode():
            out_c.mux(pk)
    if not frames:
        raise ValueError('The exported recording contains no video frames')
    samples, offset = [], -0.1
    for i, f in enumerate(m['frames']):
        ref = np.asarray(Image.open(manifest.parent/f['file']).convert('L').resize((104, 60)), dtype=float)
        # Search only around the expected time: a looping or static scene makes distant frames look alike, and the
        # first frames of an export are low quality. A gross offset still fails the error cap below.
        expected = min(len(small)-1, round(max(0, i*.5+offset)*10))
        span = 20 if (adaptive and i == 0) else 6
        lo, hi = max(0, expected-span), min(len(small), expected+span+1)
        errors = {j: float(np.abs(ref-small[j]).mean()) for j in range(lo, hi)}
        best = min(errors.values())
        k = min((j for j, e in errors.items() if e <= best+.15), key=lambda j: abs(j-expected))
        if errors[k] > (12.0 if i < 4 else 5.0):  # export warm-up frames are noisy
            raise ValueError(f'Snapshot {i} does not match the original stream (difference {errors[k]:.1f})')
        if adaptive and i == 0:
            offset = k/10
        samples.append(dict(index=i, timestamp=f['timestamp_utc'], mediaTime=round(k/10, 3),
                            matchError=round(errors[k], 2)))
    # Sampling is 2 Hz; the matched frame must lie within one native frame of i*0.5.
    for s_ in samples:
        if abs(s_['mediaTime']-max(0, s_['index']*.5+offset)) > .1001:
            raise ValueError(f"Snapshot {s_['index']} does not align with the original stream")
    info = dict(file='original.mp4', sha256=sha(target), sourceMkvSha256=m['mkv_export']['sha256'], fps=10,
                frames=len(frames), duration=len(frames)/10, firstStreamPts=frames[0], samples=samples,
                note='mediaTime = stream pts minus first pts; each manifest snapshot was matched to its decoded frame.',
                **(dict(exportOffset=offset) if adaptive else {}))
    (out/'media.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    diffs = [float(np.abs(a-b).mean()) for a, b in zip(small, small[1:])]
    return info, diffs


# -- loop phase: the camera replays one short clip, so find where it restarts ------------------------
def _gray_frames(manifest):
    from datetime import datetime
    import numpy as np
    from PIL import Image
    manifest = Path(manifest)
    m = read(manifest)
    times = [datetime.fromisoformat(f['timestamp_utc'].replace('Z', '+00:00')).timestamp() for f in m['frames']]
    arrays = [np.asarray(Image.open(manifest.parent/f['file']).convert('L').resize((104, 60)), dtype=float) for f in m['frames']]
    return times, arrays


def locate_seam(manifest, reference, period=15.0, cycle_out=None):
    """Find clip restarts in a >period-long, densely sampled recording by matching the reference clip's first frames.

    Returns dict(seam_utc, period, seams, score, contrast, cycle_repeat_error). `seam_utc` is the instant the clip is
    at position 0. With `cycle_out`, saves one full cycle (every sample, downscaled gray) for later window checks,
    because the reference recording itself is shorter than the cycle.
    """
    import numpy as np
    from datetime import datetime, timezone
    times, frames = _gray_frames(manifest)
    rt, ref = _gray_frames(reference)
    dt = float(np.median(np.diff(times)))
    probes = [(m_, round((rt[m_]-rt[0])/dt)) for m_ in range(4)]
    scores = []
    for j in range(len(frames)-max(o for _, o in probes)):
        scores.append(float(np.mean([np.abs(frames[j+o]-ref[m_]).mean() for m_, o in probes])))
    if not scores:
        raise ValueError('Calibration recording is too short')
    seams = []
    for j in np.argsort(scores):
        if scores[j] > 3*min(scores)+1.0:
            break
        if all(abs(times[j]-times[s]) > period*.5 for s in seams):
            seams.append(int(j))
    contrast = float(np.median(scores))/max(min(scores), .05)
    if not seams or contrast < 3:
        raise ValueError('Could not find the clip start in the recording')
    seams.sort()
    measured = (times[seams[-1]]-times[seams[0]])/(len(seams)-1) if len(seams) > 1 else period
    n = round(period/dt)
    j = seams[0]
    if j+n > len(frames):
        raise ValueError('Calibration recording does not hold a full cycle after the restart')
    # With a second full cycle available, the clip must repeat frame for frame.
    repeat = float(np.mean([np.abs(frames[j+i]-frames[j+n+i]).mean() for i in range(n)])) if j+2*n <= len(frames) else None
    if cycle_out:
        np.savez_compressed(cycle_out, positions=np.array([times[j+i]-times[j] for i in range(n)]),
                            frames=np.stack([frames[j+i] for i in range(n)]).astype('uint8'))
    stamp = datetime.fromtimestamp(times[j], timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'
    return dict(seam_utc=stamp, period=round(measured, 3), seams=len(seams), score=round(scores[j], 3),
                contrast=round(contrast, 1), sample_s=round(dt, 3), cycle_repeat_error=None if repeat is None else round(repeat, 3))


def verify_window(manifest, cycle, offset, max_error=3.0):
    """Check each acquired snapshot against the saved cycle frame at its expected clip position."""
    import numpy as np
    times, frames = _gray_frames(manifest)
    data = np.load(cycle)
    rpos, ref = data['positions'], data['frames'].astype(float)
    positions, errors = [], []
    for t, f in zip(times, frames):
        pos = offset+(t-times[0])
        k = int(np.argmin(np.abs(rpos-pos)))
        if abs(rpos[k]-pos) > .06 or pos > rpos[-1]:
            return dict(ok=False, reason='The window runs past the end of the clip cycle', firstPosition=round(offset, 2),
                        lastPosition=round(pos, 2))
        positions.append(pos)
        errors.append(float(np.abs(f-ref[k]).mean()))
    wrap = float(np.abs(frames[-1]-ref[0]).mean())
    ok = max(errors) <= max_error and wrap > errors[-1]+1.0
    return dict(ok=bool(ok), firstPosition=round(positions[0], 2), lastPosition=round(positions[-1], 2),
                maxError=round(max(errors), 2), meanError=round(sum(errors)/len(errors), 2),
                lastVsStartError=round(wrap, 2), frames=len(frames),
                reason=None if ok else 'The snapshots do not follow the clip cycle frame for frame')
