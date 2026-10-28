"""Re-encode an original XProtect MKV as a browser MP4, frame for frame, and verify snapshot alignment.

Importable form of scripts/adaptive_watch/prepare_review_media.py. av, numpy and PIL are imported lazily.
"""
from fractions import Fraction
import json
from pathlib import Path
import sys

from adaptive_watch.negative_review import read, sha


def prepare(manifest, out, deps=None):
    """Return (media_info, native_frame_diffs). Raises ValueError if any snapshot does not align."""
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
    samples = []
    for i, f in enumerate(m['frames']):
        ref = np.asarray(Image.open(manifest.parent/f['file']).convert('L').resize((104, 60)), dtype=float)
        # Search only around the expected time: a looping or static scene makes distant frames look alike, and the
        # first frames of an export are low quality. A gross offset still fails the error cap below.
        expected = min(len(small)-1, round(max(0, i*.5-.1)*10))
        lo, hi = max(0, expected-6), min(len(small), expected+7)
        errors = {j: float(np.abs(ref-small[j]).mean()) for j in range(lo, hi)}
        best = min(errors.values())
        k = min((j for j, e in errors.items() if e <= best+.15), key=lambda j: abs(j-expected))
        if errors[k] > (12.0 if i < 4 else 5.0):  # export warm-up frames are noisy
            raise ValueError(f'Snapshot {i} does not match the original stream (difference {errors[k]:.1f})')
        samples.append(dict(index=i, timestamp=f['timestamp_utc'], mediaTime=round(k/10, 3),
                            matchError=round(errors[k], 2)))
    # Sampling is 2 Hz; the matched frame must lie within one native frame of i*0.5.
    for s_ in samples:
        if abs(s_['mediaTime']-max(0, s_['index']*.5-.1)) > .1001:
            raise ValueError(f"Snapshot {s_['index']} does not align with the original stream")
    info = dict(file='original.mp4', sha256=sha(target), sourceMkvSha256=m['mkv_export']['sha256'], fps=10,
                frames=len(frames), duration=len(frames)/10, firstStreamPts=frames[0], samples=samples,
                note='mediaTime = stream pts minus first pts; each manifest snapshot was matched to its decoded frame.')
    (out/'media.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    diffs = [float(np.abs(a-b).mean()) for a, b in zip(small, small[1:])]
    return info, diffs
