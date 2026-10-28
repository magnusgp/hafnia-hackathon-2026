"""Re-encode the original XProtect MKV as a browser MP4, frame for frame (no resampling).

Verifies every manifest snapshot against the decoded stream before writing the time map.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adaptive_watch.negative_review import read, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--deps', type=Path, help='directory containing av, numpy, PIL')
    a = p.parse_args()
    if a.deps:
        sys.path.insert(0, str(a.deps.resolve()))
    import av
    import numpy as np
    from PIL import Image
    m = read(a.manifest)
    src = a.manifest.parent/m['mkv_export']['file']
    if sha(src) != m['mkv_export']['sha256']:
        raise ValueError('Original MKV hash mismatch')
    a.out.mkdir(parents=True, exist_ok=True)
    target = a.out/'original.mp4'
    small, frames = [], []
    with av.open(str(src)) as inp, av.open(str(target), 'w') as out:
        s = inp.streams.video[0]
        o = out.add_stream('libx264', rate=10)
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
                out.mux(pk)
        for pk in o.encode():
            out.mux(pk)
    samples = []
    for i, f in enumerate(m['frames']):
        ref = np.asarray(Image.open(a.manifest.parent/f['file']).convert('L').resize((104, 60)), dtype=float)
        errors = [np.abs(ref-b).mean() for b in small]
        k = int(np.argmin(errors))
        samples.append(dict(index=i, timestamp=f['timestamp_utc'], mediaTime=round(k/10, 3),
                            matchError=round(float(errors[k]), 2)))
    # Sampling is 2 Hz; the matched frame must lie within one native frame of i*0.5.
    for s_ in samples:
        if abs(s_['mediaTime']-max(0, s_['index']*.5-.1)) > .1001:
            raise ValueError(f"Snapshot {s_['index']} does not align with the original stream")
    info = dict(file='original.mp4', sha256=sha(target), sourceMkvSha256=m['mkv_export']['sha256'], fps=10,
                frames=len(frames), duration=len(frames)/10, firstStreamPts=frames[0], samples=samples,
                note='mediaTime = stream pts minus first pts; each manifest snapshot was matched to its decoded frame.')
    (a.out/'media.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(json.dumps(dict(sha256=info['sha256'], frames=len(frames), maxError=max(x['matchError'] for x in samples[1:]))))


if __name__ == '__main__':
    main()
