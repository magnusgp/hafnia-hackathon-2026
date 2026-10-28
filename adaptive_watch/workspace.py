"""Source-verified saved assessments and case-scoped, local operator decisions.

No inference, native dispatch, or VMS configuration capability lives here.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from adaptive_watch.evidence_api import EvidenceStore
from adaptive_watch.evaluation import parse_result
from adaptive_watch.negative_review import Conflict, ReviewStore, digest, read, seconds, sha
from adaptive_watch.obstruction import measure
from scene_contracts.gateway import video_uri

CASES = ('railway', 'gate', 'scooter', 'bin')
TITLES = dict(railway='Check the platform edge', gate='Review the school gate',
              scooter='Review the scooter placement', bin='Review the tipped bin')


class Workspace:
    def __init__(self, repo, root, railway, evaluations):
        self.repo, self.root, self.railway, self.evaluations = map(Path, (repo, root, railway, evaluations))
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root/'workspace.sqlite3', timeout=15)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS reviews(case_id TEXT PRIMARY KEY, state TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS review_audit(id INTEGER PRIMARY KEY, case_id TEXT, at TEXT, document TEXT);
          CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON review_audit BEGIN SELECT RAISE(ABORT,'append only'); END;
          CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON review_audit BEGIN SELECT RAISE(ABORT,'append only'); END;
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def catalog_match(self, camera, guid):
        matches = [c for c in read(self.repo/'cameras.local.json')
                   if c['Name'] == camera and c['Id'].lower() == guid.lower()]
        if len(matches) != 1:
            raise ValueError('Source camera does not match the authorized local catalog')

    def manifest(self, expected_hash):
        matches = [p for p in (self.repo/'runs/xprotect').glob('*/manifest.json') if sha(p) == expected_hash]
        if len(matches) != 1:
            raise ValueError('Original acquisition manifest unavailable or ambiguous')
        return matches[0]

    def raw_sources(self):
        return {sha(p): p for p in self.evaluations.glob('*.json')}

    def sidewalk(self, identifier):
        source = self.repo/'runs/hybrid/sidewalk-v2'
        joined = source/f'{identifier}-joined.json'
        e = read(joined)
        manifest = self.manifest(e['manifest_sha256'])
        cv_path = source/(e['camera_name']+'.json')
        # Reuse the existing exact camera/interval/request/frame/CV/temporal-policy
        # validator. Re-register on every read, including every served frame.
        verifier = EvidenceStore(self.root/'validation'/identifier)
        try:
            verifier.register(joined, cv_path, manifest, self.evaluations)
        finally:
            verifier.close()
        self.catalog_match(e['camera_name'], e['camera_guid'])
        measurements = json.loads(json.dumps(measure(e['local_cv']['observations'])))
        if measurements != e['measurements']:
            raise ValueError('Saved measurements differ from the original timestamped observations')
        frames = []
        for i, (row, selected) in enumerate(zip(e['local_cv']['observations'], measurements['trajectory'])):
            frames.append(dict(index=i, timestamp=row['timestamp_utc'], path=str((manifest.parent/row['file']).resolve()),
                               box=selected['object']['box'] if selected['object'] else None))
        return dict(id=identifier, title=TITLES[identifier], camera=e['camera_name'], cameraGuid=e['camera_guid'],
                    interval=e['interval_utc'], category='Supporting evidence', verificationRecommended=True,
                    summary='Hafnia supports a left object; local CV measures bounded stationarity in the same interval.',
                    evidence='Timestamped local CV stationarity and box/walkway overlap; original snapshots available. No saved original video.',
                    frames=frames, hafnia=e['hafnia'], runs=measurements['qualifying_runs'],
                    polygon=e['local_cv']['scene']['walkway'], model=e['local_cv']['model'],
                    limitations=e['limitations'], sourceRevision=digest([sha(joined),sha(cv_path),sha(manifest)]))

    def gate(self):
        source = self.repo/'runs/hybrid/sidewalk-v2/semantic-adjudication.json'
        adjudication = read(source)
        rows = [r for r in adjudication['records'] if r['original_saved_record']['entry']['scene'] == 'school_gate_break_in_night']
        if len(rows) != 2:
            raise ValueError('Both original gate prompt variants are required')
        raw_sources = self.raw_sources()
        frames, hafnia, source_hashes = [], [], [sha(source)]
        for row in rows:
            raw_path = raw_sources.get(row['original_sha256'])
            if raw_path is None or read(raw_path) != row['original_saved_record']:
                raise ValueError('Original gate Hafnia response unavailable or changed')
            raw = read(raw_path)
            entry, request, summary = raw['entry'], raw['request'], raw['summary']
            manifest = self.manifest(raw['manifest_sha256'])
            m = read(manifest)
            self.catalog_match(m['camera_name'], m['camera_id'])
            expected = video_uri(m['camera_id'], *[datetime.fromisoformat(entry[k].replace('Z','+00:00')) for k in ('start','end')])
            returned = summary['Request']
            if (entry['camera_id'].lower() != m['camera_id'].lower() or entry['camera_name'] != m['camera_name']
                    or request['VideoUris'] != [expected] or any(returned.get(k) != v for k,v in request.items())
                    or set(returned)-set(request)-{'AiModelId'}
                    or 'AiModelId' in returned and returned['AiModelId'] != 'traffic-general'
                    or summary['Progress'] != 'Completed'):
                raise ValueError('Gate camera, interval or request provenance mismatch')
            selected = [f for f in m['frames'] if seconds(entry['start']) <= seconds(f['timestamp_utc']) < seconds(entry['end'])]
            if (not selected or len(selected) != len(row['frames']) or
                    any(any(f.get(k) != v for k,v in original.items()) for f, original in zip(row['frames'], selected))):
                raise ValueError('Gate original frame selection mismatch')
            current = []
            for i, f in enumerate(row['frames']):
                path = (manifest.parent/f['file']).resolve()
                if not path.is_relative_to(manifest.parent.resolve()) or sha(path) != f['sha256']:
                    raise ValueError('Gate original frame unavailable or changed')
                current.append(dict(index=i,timestamp=f['timestamp_utc'],path=str(path),box=None))
            if frames and frames != current:
                raise ValueError('Gate prompt variants refer to different recordings')
            frames = current
            parsed = parse_result(summary)
            if parsed.get('outcome') != 'not_observed' or not parsed.get('evidence'):
                raise ValueError('Original negative gate conclusion cannot be verified')
            hafnia.append(dict(summary_id=summary['Id'],original_response=summary['Response'],request=request,parsed=parsed))
            source_hashes.extend([sha(raw_path),sha(manifest)])
        diagnostic = self.gate_diagnostic()
        return dict(id='gate',title=TITLES['gate'],camera=m['camera_name'],cameraGuid=m['camera_id'],
                    interval=[entry['start'],entry['end']],category='Semantic uncertainty',verificationRecommended=True,
                    summary='Original negative conclusions describe tool/lock manipulation but require successful opening. No independent CV corroboration.',
                    evidence='Two original prompt variants and timestamped snapshots. Independent CV and original video unavailable.',
                    frames=frames,hafnia=hafnia,runs=[],polygon=None,model=None,
                    limitations=['Tool/lock detail is partially occluded. Opening, entry, damage and criminal intent are not established.',
                                 'Prompt variants assess the same recording; they are not independent events.'],
                    diagnostic=diagnostic, sourceRevision=digest([source_hashes,diagnostic]))

    def gate_diagnostic(self):
        """Separate later recording: preserve dates; never align its claims to old frames."""
        report = read(self.repo/'results/reliability/completed-diagnostic-24.json')
        ledger = self.repo/'runs/reliability-diagnostics/operator-batch/reliability-ledger.sqlite3'
        db = sqlite3.connect(f'file:{ledger.resolve().as_posix()}?mode=ro',uri=True)
        try:
            rows = db.execute('SELECT experiment,summary_id,state,payload,result FROM requests WHERE experiment LIKE ?',('%-gate-%',)).fetchall()
        finally:
            db.close()
        if len(rows) != 12:
            raise ValueError('Gate diagnostic originals unavailable')
        responses = []
        import hashlib
        for experiment, sid, state, payload, result in rows:
            item = next(r for r in report['results'] if r['experiment_id'] == experiment)
            raw, payload = json.loads(result)['raw'], json.loads(payload)
            envelope_hash = hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()
            if (state != 'valid_descriptive_response' or raw['Id'] != sid or sid != item['summary_id']
                    or raw['Progress'] != 'Completed' or envelope_hash != item['returned_envelope_sha256']
                    or any(raw['Request'].get(k) != v for k,v in payload.items())):
                raise ValueError('Gate diagnostic response integrity mismatch')
            manifests = [p for p in (self.repo/'runs/reliability-diagnostics/selected').glob('*/manifest.json') if sha(p) == item['source_manifest_sha256']]
            if len(manifests) != 1:
                raise ValueError('Separate diagnostic recording unavailable')
            m = read(manifests[0])
            self.catalog_match(m['camera_name'],m['camera_id'])
            expected = video_uri(m['camera_id'], *[datetime.fromisoformat(item[k].replace('Z','+00:00')) for k in ('start','end')])
            video = manifests[0].parent/m['mkv_export']['file']
            if (m['camera_name'] != 'school_gate_break_in_night' or payload['VideoUris'] != [expected]
                    or sha(video) != item['video_sha256']):
                raise ValueError('Gate diagnostic source identity mismatch')
            responses.append(dict(summaryId=sid,prompt=payload['Prompt'],response=raw['Response'],family=item['family'],
                                  interval=[item['start'],item['end']]))
        return dict(note='Separate 27 October recording; prompt-sensitive handling descriptions. No independent CV. These responses do not describe the 22 October frames.',responses=responses)

    def record(self, identifier):
        if identifier not in CASES:
            raise KeyError('Unknown assessment')
        if identifier == 'railway':
            store = ReviewStore(self.railway)
            try:
                view = store.view()
                self.catalog_match(view['camera'],view['cameraGuid'])
                return dict(id='railway',title=TITLES['railway'],camera=view['camera'],cameraGuid=view['cameraGuid'],
                            interval=view['interval'],category='Review recommended' if view['trigger'] else 'Insufficient evidence',
                            verificationRecommended=True,summary='Hafnia: entry not observed. Local CV: person/region proximity; entry is not confirmed.' if view['trigger'] else 'Hafnia: entry not observed. No configured person/region proximity condition.',
                            evidence='Local person/region proximity; timestamped snapshots and original recording available.',state=view['state'])
            finally:
                store.close()
        return self.gate() if identifier == 'gate' else self.sidewalk(identifier)

    def view(self, identifier, private=False):
        record = self.record(identifier)
        if identifier == 'railway':
            return record
        row = self.db.execute('SELECT state FROM reviews WHERE case_id=?',(identifier,)).fetchone()
        state = json.loads(row[0]) if row else dict(status='review_required',version=0,humanAnnotation=None,reviewed=False)
        record['state'] = state
        record['revision'] = digest([identifier,record['sourceRevision'],state])
        if not private:
            record['frames'] = [{k:v for k,v in f.items() if k != 'path'} | dict(file=f'/api/cases/{identifier}/frames/{f["index"]}') for f in record['frames']]
            record.pop('sourceRevision')
        return record

    def index(self):
        records, unavailable = [], []
        for identifier in CASES:
            try:
                record = self.view(identifier)
                records.append({k:record[k] for k in ('id','title','camera','interval','category','verificationRecommended','summary','evidence','state')})
            except (ValueError,TypeError,KeyError,OSError,sqlite3.Error,StopIteration):
                unavailable.append(dict(id=identifier,error='Insufficient evidence: source verification failed. Restore the original recording, response and CV sources before reviewing.'))
        return dict(records=records,unavailable=unavailable)

    def act(self, identifier, body):
        if identifier == 'railway':
            raise ValueError('Use the preserved railway review controls')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            view = self.view(identifier)
            if body.get('revision') != view['revision']:
                raise Conflict('Evidence or review changed; reload before deciding')
            state, action = view['state'], body.get('action')
            note = body.get('note','')
            if not isinstance(note,str) or len(note)>2000:
                raise ValueError('Review note must be at most 2000 characters')
            if action == 'review':
                state.update(status='reviewing',reviewed=True)
            elif action in {'dismiss','save_review_request'}:
                if state['status'] != 'reviewing' or body.get('footageReviewed') is not True:
                    raise ValueError('Review the footage and acknowledge it before deciding')
                annotation = body.get('annotation','not_verified')
                if annotation not in {'not_verified','condition_visible','condition_not_visible','uncertain'}:
                    raise ValueError('Unknown visible-condition annotation')
                if annotation != 'not_verified' and not note.strip():
                    raise ValueError('Describe the footage supporting your annotation')
                state.update(status='dismissed' if action == 'dismiss' else 'review_request_saved',
                             humanAnnotation=dict(value=annotation,note=note.strip(),at=datetime.now(timezone.utc).isoformat(),
                                                  provenance='Local operator attestation; identity is not authenticated'))
            else:
                raise ValueError('Unsupported local review action; native dispatch unavailable')
            state['version'] += 1
            self.db.execute('INSERT INTO reviews VALUES (?,?) ON CONFLICT(case_id) DO UPDATE SET state=excluded.state',(identifier,json.dumps(state)))
            self.db.execute('INSERT INTO review_audit(case_id,at,document) VALUES (?,?,?)',
                            (identifier,datetime.now(timezone.utc).isoformat(),json.dumps(dict(action=action,revision=view['revision'],state=state))))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.view(identifier)
