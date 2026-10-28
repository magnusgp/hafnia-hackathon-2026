"""Collect deck assets from the verified casebook. Footage stays in git-ignored presentation/assets."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adaptive_watch.casebook import Casebook

EVALUATIONS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/Users/Administrator/adaptive-watch-private/hafnia-16')
out = ROOT/'presentation'
(out/'assets').mkdir(exist_ok=True)
(out/'fonts').mkdir(exist_ok=True)
book = Casebook(ROOT, ROOT/'runs/release/demo-app', ROOT/'runs/release/demo-railway', EVALUATIONS, ROOT/'runs/release')
try:
    v = book.view('railway')
finally:
    book.close()
shutil.copyfile(ROOT/'runs/release/media/railway/original.mp4', out/'assets/railway.mp4')
region = v['vision']['region']['polygon']
data = dict(origin=v['video']['origin'], duration=v['video']['duration'], region=region,
            trigger=v['vision']['trigger']['mediaTime'], decisive=v['agent']['decisiveMoment']['mediaTime'],
            samples=[dict(t=f['mediaTime'], box=f['box'], near=f['near'], ts=f['timestamp']) for f in v['frames']])
(out/'assets/samples.json').write_text(json.dumps(data), encoding='utf-8')
files = ROOT/'frontend/node_modules/@fontsource'
for family, weights in (('space-grotesk', (500, 600)), ('dm-sans', (400, 500, 600)), ('ibm-plex-mono', (400,))):
    for w in weights:
        name = f'{family}-latin-{w}-normal.woff2'
        shutil.copyfile(files/family/'files'/name, out/'fonts'/name)
print('assets ready:', len(data['samples']), 'samples')
