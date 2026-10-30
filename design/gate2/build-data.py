"""Pull the real Ortru records the prototypes show. GET requests only, nothing is written to Ortru.

    .venv\\Scripts\\python.exe -I design\\gate2\\build-data.py [http://127.0.0.1:8790]

Writes design/gate2/generated/ (git-ignored: it holds footage, camera frames and review text):
  data.js        window.ORTRU = {...}, a trimmed copy of the real API responses
  media/         the recording and 24 evidence frames of the occurrence, camera frames
  fonts/         the woff2 files the Ortru frontend already ships
"""
import json, pathlib, shutil, sys, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8790'
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'generated'
FONTS = HERE.parents[1] / 'frontend' / 'node_modules' / '@fontsource'
SENT = 'b586966c61d7460c997bcc47b0a3ce38'


def get(path, raw=False):
    with urllib.request.urlopen(BASE + path) as r:
        body = r.read()
    return body if raw else json.loads(body.decode('utf-8-sig'))['data']


def save(path, data):
    path = OUT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


boot, queue = get('/api/ortru'), get('/api/queue')
members = []
for q in queue['live']:
    v = get('/api/exceptions/' + q['id'])
    members.append(dict(
        id=v['id'], interval=v['interval'], at=v['at'], watch=v['watch'], camera=v['camera'], hafnia=v['hafnia'], policy=v['policy'],
        decision=v['decision'], native=v['native'], vision=v['vision'], video=dict(duration=v['video']['duration'], sha256=v['video']['sha256']),
        requestSha256=v['provenance']['hafniaRequestSha256'], event=v['event']['key'], limitations=v['limitations'], review=v['review']))
members.sort(key=lambda m: m['at'])
history = get(f'/api/exceptions/{SENT}/history')
sent = next(m for m in members if m['id'] == SENT)

save('media/occurrence.mp4', get(f'/api/exceptions/{SENT}/video', raw=True))
for i in range(len(sent['vision']['samples'])):
    save(f'media/frame-{i:02d}.jpg', get(f'/api/exceptions/{SENT}/frames/{i}', raw=True))
for c in boot['cameras']:
    if c['hasSnapshot']:
        save(f"media/camera-{c['name']}.jpg", get(f"/api/cameras/{c['id']}/snapshot", raw=True))

watches = []
for w in boot['watches']:
    jobs = [dict(state=j['state'], trigger=j['trigger'], interval=j['interval'], error=j['error'], created=j['created'], exceptionId=j.get('exceptionId')) for j in w['jobs'][:3]]
    watches.append(dict(id=w['id'], status=w['status'], config=w['config'], schedule=w['schedule'], jobs=jobs, history=w['history'][-4:], hasSnapshot=w['hasSnapshot']))

data = dict(
    gateway=boot['gateway'], native=boot['native'], budget=boot['budget'],
    cameras=[dict(id=c['id'], name=c['name'], hasSnapshot=c['hasSnapshot'], alarm=c['native']) for c in boot['cameras']],
    capabilities=[dict(id=c['id'], label=c['label'], available=c['available'], needsRegion=c['needsRegion'], establishes=c['establishes']) for c in boot['capabilities']],
    policyKinds=boot['policyKinds'], watches=watches, members=members, history=history, records=queue['records'], sentId=SENT,
    # Alarm 10 was opened in Smart Client by the product owner on 30 Oct (evidence: ortru-gate1/smart-client-verification-alarm10.md).
    # The running API still reports smartClient "not_verified": nothing records that outcome yet, so it is overlaid here.
    alarm=dict(localId=10, verifiedBy='product owner', verifiedOn='2026-10-30', sourceTime='2026-10-29T12:42:29.513Z'),
)
for f in ('space-grotesk/files/space-grotesk-latin-500-normal.woff2', 'space-grotesk/files/space-grotesk-latin-600-normal.woff2',
          'dm-sans/files/dm-sans-latin-400-normal.woff2', 'dm-sans/files/dm-sans-latin-500-normal.woff2', 'dm-sans/files/dm-sans-latin-600-normal.woff2',
          'ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2'):
    (OUT / 'fonts').mkdir(parents=True, exist_ok=True)
    shutil.copy(FONTS / f, OUT / 'fonts' / pathlib.Path(f).name)
(OUT / 'data.js').write_text('window.ORTRU = ' + json.dumps(data, indent=1) + ';\n', encoding='utf-8')
print('wrote', OUT, len(members), 'observations,', len(data['watches']), 'watches')
