"""Derive scene starts, captions and total length from the rendered narration (WAV durations)."""
import json
from pathlib import Path
import re
import sys
import wave

root = Path(__file__).resolve().parent
spec = json.loads((root/'narration.json').read_text(encoding='utf-8'))
audio = root/'assets/audio'
# Minimum on-screen time per scene so footage and animation can finish; capture length overrides operator.
MINIMUM = dict(open=12.5, silent=12.5, signal=20.0, how=24.0, operator=28.0, xprotect=14.0, built=24.0, close=14.0)
LEAD, TAIL = 0.5, 1.4
if len(sys.argv) > 1:
    MINIMUM['operator'] = float(sys.argv[1])
proof = sys.argv[2] if len(sys.argv) > 2 else ''
start, scenes = 0.0, []
for s in spec['scenes']:
    with wave.open(str(audio/f"{s['id']}.wav")) as w:
        length = w.getnframes()/w.getframerate()
    dur = max(MINIMUM[s['id']], LEAD + length + TAIL)
    parts = [p.strip() for p in re.split(r'(?<=[.:?!])\s+', s['text']) if p.strip()]
    total = sum(len(p) for p in parts)
    t, sentences = LEAD, []
    for p in parts:
        d = length*len(p)/total
        sentences.append(dict(t=round(t, 2), d=round(d, 2), text=p))
        t += d
    scenes.append(dict(id=s['id'], start=round(start, 2), dur=round(dur, 2), audioStart=round(start + LEAD, 2), audioLength=round(length, 2), sentences=sentences))
    start += dur
doc = dict(total=round(start, 2), scenes=scenes, proof=proof)
(root/'timing.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
print('total', doc['total'], [(s['id'], s['dur']) for s in scenes])
