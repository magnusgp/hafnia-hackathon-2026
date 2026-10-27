"""One saved negative-result review. Offline evidence; no native transport access."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from adaptive_watch.tracking import foot, inside

EVENT_NAME = 'Adaptive Watch Review Required'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def seconds(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def distance(point, polygon):
    """Euclidean distance in normalized image coordinates; zero inside region."""
    if inside(point, polygon):
        return 0.0
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        size = dx*dx+dy*dy
        t = max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/size)) if size else 0
        distances.append(math.hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy))
    return min(distances)


def validate_region(region):
    polygon, threshold = region['polygon'], region['threshold']
    if (not isinstance(polygon, list) or not 3 <= len(polygon) <= 12 or
            any(not isinstance(p, list) or len(p) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in polygon) or
            type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= .1):
        raise ValueError('Use 3–12 normalized points and a proximity margin between 0 and 0.1')
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon,polygon[1:]+polygon[:1])))/2
    if area < .001:
        raise ValueError('Attention region is too small or degenerate')
    if len({tuple(p) for p in polygon}) != len(polygon):
        raise ValueError('Attention region corners must be distinct')
    def turn(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    edges = list(zip(polygon,polygon[1:]+polygon[:1]))
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges):
            if j <= i or j == i+1 or (i == 0 and j == len(edges)-1):
                continue
            if turn(a,b,c)*turn(a,b,d) <= 0 and turn(c,d,a)*turn(c,d,b) <= 0:
                raise ValueError('Draw the corners in order around the region; edges must not cross')
    return dict(polygon=polygon, threshold=threshold)


def build_record(repo, response, media):
    """Import exact October 22 CV/response plus separately dated diagnostic context."""
    repo, response, media = Path(repo).resolve(), Path(response).resolve(), Path(media).resolve()
    cv_path = repo/'runs/hybrid/railway-cv-1163ddf.json'
    manifest_path = repo/'runs/xprotect/person_on_railway_tracks_20261022T110339Z/manifest.json'
    audit_path = repo/'runs/reliability-20261026/saved-response-audit.private.json'
    diagnostic_path = repo/'results/reliability/completed-diagnostic-24.json'
    cv_audit_path = repo/'results/reliability/railway-frame-audit.json'
    cv, m, raw, diagnostic = map(read, (cv_path, manifest_path, response, diagnostic_path))
    audited = next(r for r in read(audit_path) if r['source_sha256'] == sha(response))
    e, summary = raw['entry'], raw['summary']
    parsed = audited['parsed']
    literal = summary['Response'].strip()
    if literal.startswith('```'):
        literal = '\n'.join(literal.splitlines()[1:-1])
    original_decision = json.loads(literal)
    if (sha(cv_path) != read(cv_audit_path)['source_sha256'] or
            cv['manifest_sha256'] != sha(manifest_path) or raw['manifest_sha256'] != sha(manifest_path) or
            cv['source_manifest'] != m or
            e['camera_id'].lower() != m['camera_id'].lower() or e['camera_name'] != m['camera_name'] or
            [seconds(e[k]) for k in ('start','end')] != [seconds(m[k]) for k in ('requested_start_utc','requested_end_utc')] or
            audited['original_summary'] != summary or audited['original_request'] != raw['request'] or
            parsed['outcome'] != 'not_observed' or summary['Progress'] != 'Completed' or
            any(original_decision[k] != parsed[k] for k in ('outcome','evidence'))):
        raise ValueError('Original railway evidence identity mismatch')
    from scene_contracts.gateway import video_uri
    expected = video_uri(m['camera_id'], *[datetime.fromisoformat(e[k].replace('Z','+00:00')) for k in ('start','end')])
    if raw['request']['VideoUris'] != [expected] or any(summary['Request'].get(k) != v for k,v in raw['request'].items()):
        raise ValueError('Hafnia request does not identify the original camera and interval')
    sources = []

    def source(path, expected_hash=None):
        path = Path(path).resolve()
        actual = sha(path)
        if expected_hash and actual != expected_hash:
            raise ValueError('Original source hash mismatch: '+path.name)
        sources.append(dict(path=str(path), sha256=actual))

    for path in (cv_path, manifest_path, response, audit_path, diagnostic_path, cv_audit_path):
        source(path)
    source(manifest_path.parent/m['mkv_export']['file'], m['mkv_export']['sha256'])
    frames = []
    if len(cv['observations']) != len(m['frames']):
        raise ValueError('CV sample count differs from original recording')
    start = seconds(m['frames'][0]['timestamp_utc'])
    for i, (f, observation) in enumerate(zip(m['frames'], cv['observations'])):
        if f['timestamp_utc'] != observation['timestamp_utc'] or abs(seconds(f['timestamp_utc'])-start-i*.5) > .0001:
            raise ValueError('CV timestamp or sample spacing mismatch')
        path = (manifest_path.parent/f['file']).resolve()
        if not path.is_relative_to(manifest_path.parent):
            raise ValueError('Invalid source frame path')
        source(path, f['sha256'])
        selected = [o for o in observation['objects'] if o['track_id'] == 7]
        if len(selected) > 1:
            raise ValueError('Ambiguous selected track sample')
        frames.append(dict(index=i, timestamp=f['timestamp_utc'], mediaTime=i*.5,
                           path=str(path), sha256=f['sha256'], box=selected[0]['box'] if selected else None))
    # Audit all 24 original diagnostic envelopes, without joining their dates to CV.
    ledger = repo/'runs/reliability-diagnostics/operator-batch/reliability-ledger.sqlite3'
    db = sqlite3.connect(f'file:{ledger.as_posix()}?mode=ro', uri=True)
    try:
        rows = db.execute('SELECT experiment,summary_id,state,payload,result FROM requests').fetchall()
    finally:
        db.close()
    results = diagnostic['results']
    if (len(rows) != 24 or len(results) != 24 or diagnostic['completed_requests'] != 24 or
            diagnostic['semantic_counts']['railway'] != {'asserts_entry_or_occupancy':3,'platform_only_or_denies_entry':9}):
        raise ValueError('Completed diagnostic must contain exactly 24 originals')
    for experiment, sid, state, payload, saved in rows:
        result = next(r for r in results if r['experiment_id'] == experiment)
        payload, original = json.loads(payload), json.loads(saved)['raw']
        if (state != 'valid_descriptive_response' or sid != result['summary_id'] or original['Id'] != sid or
                original['Progress'] != 'Completed' or hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest() != result['returned_envelope_sha256'] or
                hashlib.sha256(original['Response'].encode()).hexdigest() != result['response_sha256'] or
                any(original['Request'].get(k) != v for k,v in payload.items())):
            raise ValueError('Diagnostic response integrity mismatch')
    source(ledger)
    media_info = read(media/'media.json')
    if media_info['frameHashes'] != [f['sha256'] for f in frames]:
        raise ValueError('Video was not derived from these exact timestamped frames')
    source(media/'media.json')
    source(media/'railway-samples.mp4', media_info['sha256'])
    proximity_samples = [dict(timestamp=f['timestamp'],frameIndex=f['index'],distance=distance(foot(f['box']),cv['zone']['polygon']))
                         for f in frames if f['box']]
    first = next(f for f in proximity_samples if f['distance'] == 0)
    automated = dict(condition='negative_hafnia_and_person_proximity',trackId=7,
        region=cv['zone'],threshold=0,units='normalized image coordinates; not metres',samples=proximity_samples,
        firstProximity=first,entryConfirmed=False,
        reason=f'Hafnia returned not_observed; track 7 bounding-box bottom has zero distance to the configured attention region at {first["timestamp"]}. Proximity requests review and does not confirm entry.')
    return dict(schemaVersion=1, id='railway-negative-review', camera=m['camera_name'], cameraGuid=m['camera_id'],
                interval=[e['start'],e['end']], hafnia=dict(outcome=parsed['outcome'], conclusion=parsed['evidence'],
                summaryId=summary['Id'], originalResponse=summary['Response'], originalRequest=raw['request']),
                cv=dict(trackId=7, model=cv['model'], revision=cv['revision'], zone=cv['zone'],
                        limitation='Track 7 is an association hypothesis. Missing boxes stay missing; approach track 1 is not merged.'),
                frames=frames, media=dict(path=str(media/'railway-samples.mp4'), duration=len(frames)*.5,
                source='Original recorded snapshots, 0.5 s samples', timestampOrigin=frames[0]['timestamp']),
                reference=dict(provenance='AI-reviewed calibration reference; not human-verified',
                entryBracket=['2026-10-22T11:03:48.013Z','2026-10-22T11:03:48.513Z']),
                diagnostic=dict(completed=24, railwayResponses=12, railwayEntryClaims=3, railwayOtherClaims=9,
                sourceInterval=['2026-10-27T11:55:38Z','2026-10-27T11:55:51Z'],
                note='Separate recording interval. Claim counts are diagnostic findings, not model accuracy.'),
                native=dict(eventName=EVENT_NAME, configured=False, dispatchAvailable=False,
                reason='Separate authorization is required for event/alarm configuration and each native dispatch.'),
                automatedFindings=automated,humanVerifiedEntry=dict(status='not_verified',annotation=None),
                availableActions=['Review footage','Dismiss after review','Request XProtect review after review'],
                sources=sources, originalVideo=str(manifest_path.parent/m['mkv_export']['file']))


class Conflict(ValueError):
    pass


class ReviewStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root/'review.sqlite3', timeout=15)
        self.db.execute('CREATE TABLE IF NOT EXISTS review (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT, digest TEXT, state TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS review_audit (id INTEGER PRIMARY KEY, at TEXT, action TEXT, document TEXT)')
        self.db.commit()

    def close(self):
        self.db.close()

    def install(self, record):
        if self.db.execute('SELECT 1 FROM review').fetchone():
            raise ValueError('Review already imported; use its existing workflow')
        region = validate_region(dict(polygon=record['cv']['zone']['polygon'], threshold=0))
        state = dict(status='review_required', region=region, version=0, humanAnnotation=None, reviewed=False)
        with self.db:
            self.db.execute('INSERT INTO review VALUES (1,?,?,?)', (json.dumps(record),digest(record),json.dumps(state)))
        return self.view()

    def verified(self):
        row = self.db.execute('SELECT record,digest,state FROM review WHERE id=1').fetchone()
        if not row:
            raise ValueError('No persisted railway review has been imported')
        record, state = json.loads(row[0]), json.loads(row[2])
        if digest(record) != row[1]:
            raise Conflict('Review record integrity check failed')
        for source in record['sources']:
            if sha(source['path']) != source['sha256']:
                raise Conflict('Original evidence changed; review is blocked')
        return record, state

    def view(self):
        record, state = self.verified()
        frames = []
        for f in record['frames']:
            d = distance(foot(f['box']),state['region']['polygon']) if f['box'] else None
            frames.append(dict(index=f['index'], timestamp=f['timestamp'], mediaTime=f['mediaTime'], box=f['box'],
                file=f'/api/review/frames/{f["index"]}', distance=d,
                proximity=d is not None and d <= state['region']['threshold']))
        candidates = [f for f in frames if f['proximity']]
        trigger = candidates[0] if candidates else None
        reason = (f'Hafnia returned not_observed; track 7 bounding-box bottom is {trigger["distance"]:.6f} normalized image units '
                  f'from the attention region (configured margin {state["region"]["threshold"]:.6f}) at {trigger["timestamp"]}. '
                  'This requests visual review; it does not confirm entry.') if trigger else 'No configured proximity condition in the selected track.'
        revision = digest([digest(record),state])
        return dict(id=record['id'],revision=revision,camera=record['camera'],cameraGuid=record['cameraGuid'],interval=record['interval'],
            state=state,frames=frames,hafnia=record['hafnia'],cv=record['cv'],media={**record['media'],'path':'/api/review/video'},
            trigger=trigger,reason=reason,diagnostic=record['diagnostic'],native=record['native'],reference=record['reference'],
            actions=['Review footage'], evidenceHashes=[dict(name=Path(s['path']).name,sha256=s['sha256']) for s in record['sources']])

    def act(self, body):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current = self.view()
            if body.get('revision') != current['revision']:
                raise Conflict('Evidence or review changed; reload before deciding')
            action, state = body.get('action'), current['state']
            note = str(body.get('note','')).strip()
            if len(note) > 2000:
                raise ValueError('Review note is too long')
            if action == 'configure_region':
                state.update(region=validate_region(body['region']), reviewed=False, humanAnnotation=None, status='review_required')
            elif action == 'review':
                state.update(reviewed=True, status='reviewing')
            elif action in {'dismiss','request_xprotect_review'}:
                if not state['reviewed'] or state['status'] != 'reviewing':
                    raise ValueError('Review footage before making a decision')
                if body.get('footageReviewed') is not True:
                    raise ValueError('Confirm that you reviewed the relevant footage')
                if action == 'request_xprotect_review' and not current['trigger']:
                    raise ValueError('The configured proximity condition is absent')
                annotation = body.get('annotation','not_verified')
                if annotation not in {'not_verified','entry_visible','entry_not_visible','uncertain'}:
                    raise ValueError('Unknown human entry annotation')
                if annotation != 'not_verified' and not note:
                    raise ValueError('Add a note describing the footage supporting your annotation')
                state['humanAnnotation'] = dict(value=annotation, note=note, at=datetime.now(timezone.utc).isoformat(),
                                               provenance='Local operator attestation; identity is not authenticated')
                state['status'] = 'dismissed' if action == 'dismiss' else 'xprotect_review_requested'
            else:
                raise ValueError('Unknown review action; native dispatch is unavailable')
            state['version'] += 1
            self.db.execute('UPDATE review SET state=? WHERE id=1',(json.dumps(state),))
            self.db.execute('INSERT INTO review_audit(at,action,document) VALUES (?,?,?)',
                (datetime.now(timezone.utc).isoformat(),action,json.dumps(dict(revision=current['revision'],state=state))))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.view()
