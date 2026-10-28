"""Render the final MP4: record the timed deck in a real browser, then mux the local-voice narration.

  python render.py convert <capture.webm> <out.mp4> <trim_s>   webm -> H.264 (used for the operator capture)
  python render.py mux <deck.webm> <offset_s> <out.mp4>        trim, encode H.264 1920x1080 and add narration
"""
from fractions import Fraction
import json
from pathlib import Path
import sys
import wave

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent/'runs/tooling/pydeps'))
import av
import numpy as np


def convert(src, dst, trim):
    with av.open(src) as i, av.open(dst, 'w') as o:
        s = i.streams.video[0]
        out = o.add_stream('libx264', rate=25)
        out.width, out.height, out.pix_fmt, out.options = 1920, 1080, 'yuv420p', dict(crf='17', preset='slow', movflags='faststart')
        n = 0
        for f in i.decode(video=0):
            t = float(f.pts*s.time_base)
            if t < trim:
                continue
            nf = f.reformat(width=1920, height=1080, format='yuv420p')
            nf.pts, nf.time_base = n, Fraction(1, 25)
            n += 1
            for p in out.encode(nf):
                o.mux(p)
        for p in out.encode():
            o.mux(p)
    print('frames', n, 'seconds', n/25)


def mux(src, offset, dst):
    timing = json.loads((root/'timing.json').read_text())
    total = timing['total']
    rate = 44100
    audio = np.zeros(int(total*rate), dtype=np.float32)
    for sc in timing['scenes']:
        with wave.open(str(root/f"assets/audio/{sc['id']}.wav")) as w:
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)/32768
            r = w.getframerate()
        data = np.interp(np.arange(0, len(data), r/rate), np.arange(len(data)), data)
        at = int(sc['audioStart']*rate)
        audio[at:at+len(data)] += data[:len(audio)-at]
    audio = np.clip(audio*0.9, -1, 1)
    with av.open(src) as i, av.open(dst, 'w') as o:
        s = i.streams.video[0]
        v = o.add_stream('libx264', rate=25)
        v.width, v.height, v.pix_fmt, v.options = 1920, 1080, 'yuv420p', dict(crf='17', preset='slow', movflags='faststart')
        a = o.add_stream('aac', rate=rate)
        a.layout = 'mono'
        n, limit = 0, int(total*25)
        for f in i.decode(video=0):
            t = float(f.pts*s.time_base) - offset
            if t < 0:
                continue
            if n >= limit:
                break
            nf = f.reformat(width=1920, height=1080, format='yuv420p')
            nf.pts, nf.time_base = n, Fraction(1, 25)
            n += 1
            for p in v.encode(nf):
                o.mux(p)
        for p in v.encode():
            o.mux(p)
        pcm = (audio[:int(n/25*rate)]*32767).astype(np.int16)
        for k in range(0, len(pcm), 1024):
            fr = av.AudioFrame.from_ndarray(pcm[k:k+1024].reshape(1, -1), format='s16', layout='mono')
            fr.sample_rate, fr.pts = rate, k
            fr.time_base = Fraction(1, rate)
            for p in a.encode(fr):
                o.mux(p)
        for p in a.encode():
            o.mux(p)
    print('frames', n, 'seconds', n/25)


if __name__ == '__main__':
    if sys.argv[1] == 'convert':
        convert(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    else:
        mux(sys.argv[2], float(sys.argv[3]), sys.argv[4])
