"""Copy only hash-verified saved scooter frames into ignored prototype assets."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
source = root / 'runs/hybrid/sidewalk-v2'
e = json.loads((source / 'scooter-joined.json').read_text())
out = Path(__file__).parent / 'public/private'
out.mkdir(parents=True, exist_ok=True)
frames = []
for i, observation in enumerate(e['local_cv']['observations']):
    frame = source / 'review-scooter' / f'frame-{i:04d}.jpg'
    if hashlib.sha256(frame.read_bytes()).hexdigest() != observation['sha256']:
        raise ValueError(f'Frame hash mismatch: {frame}')
    shutil.copyfile(frame, out / frame.name)
    selected = next((r['object'] for r in e['measurements']['trajectory'] if r['timestamp_utc'] == observation['timestamp_utc']), None)
    # Overlay is deliberately restricted to the selected stationary foreground hypothesis.
    stationary = observation['timestamp_utc'] >= e['measurements']['qualifying_runs'][0]['first']
    frames.append(dict(file=f'/private/{frame.name}', timestamp=observation['timestamp_utc'], box=selected['box'] if selected and stationary else None))
data = dict(frames=frames, camera=e['camera_name'], cameraGuid=e['camera_guid'], interval=e['interval_utc'],
            manifestSha256=e['manifest_sha256'], cvSha256=e['cv_sha256'], runs=e['measurements']['qualifying_runs'],
            hafnia=e['hafnia'], limitations=e['limitations'], polygon=e['local_cv']['scene']['walkway'],
            annotations=json.loads((source / 'manual-review.json').read_text())['scenes']['scooter'])
(out / 'evidence.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
print(f'Prepared {len(frames)} verified private samples at {out}')

# Inventory is a private snapshot of acquired cameras, not a live health feed.
plan = json.loads((root / 'runs/hybrid/plan.json').read_text())
config = json.loads((root / 'runs/hybrid/sidewalk-config.json').read_text())
configured = {s['name'] for s in config['scenes']}
cameras = []
for item in plan:
    if any(c['id'] == item['camera_id'] for c in cameras):
        continue
    cameras.append(dict(id=item['camera_id'], name=item['camera_name'],
                        configured=item['camera_name'] in configured,
                        role='Negative control' if item['camera_name'] == 'busy_street' else 'Saved evaluation interval'))
records = []
for key in ('scooter', 'bin'):
    joined = json.loads((source / f'{key}-joined.json').read_text())
    records.append(dict(key=key, camera=joined['camera_name'], interval=joined['interval_utc'],
                        runs=joined['measurements']['qualifying_runs'], hafniaCount=len(joined['hafnia'])))
(out / 'workspace.json').write_text(json.dumps(dict(cameras=cameras, records=records,
    sources=['runs/hybrid/plan.json', 'runs/hybrid/sidewalk-config.json', 'runs/hybrid/sidewalk-v2/*-joined.json']), indent=2), encoding='utf-8')
