"""Indexed, read-only localhost evidence service. No gateway or event-server access."""
import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from adaptive_watch.capabilities import camera_config, cameras
from adaptive_watch.incident import sha, assemble
from adaptive_watch.evaluation import parse_result
from adaptive_watch.obstruction import measure, seconds
from scene_contracts.gateway import video_uri


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root/'evidence.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    def register(self, joined, cv_path, manifest, evaluations, spatial=None):
        """Import existing evidence without upgrading its historical dispatch eligibility."""
        joined, cv_path, manifest = map(lambda p: Path(p).resolve(), (joined, cv_path, manifest))
        e = json.loads(joined.read_text(encoding='utf-8-sig'))
        cv = json.loads(cv_path.read_text(encoding='utf-8-sig'))
        m = json.loads(manifest.read_text(encoding='utf-8-sig'))
        c = camera_config(e['camera_name'], e['camera_guid'])
        scene = cv['scene']
        if (sha(cv_path) != e['cv_sha256'] or sha(manifest) != e['manifest_sha256'] or
                cv['manifest_sha256'] != sha(manifest) or cv['source_manifest'] != m or
                m['camera_id'].lower() != c['camera_guid'] or m['camera_name'] != c['name'] or
                scene['name'] != c['name'] or scene['queries'] != c['queries'] or
                e['interval_utc'] != [scene['start'],scene['end']]):
            raise ValueError('Persisted camera, interval or source provenance mismatch')
        # Fresh joins update exact polygon overlap in memory. Preserve that join while
        # verifying its observations still identify the original detector and frames.
        local = e['local_cv']
        historical = e.get('schema_version') == 1
        if historical and (local['observations'] != cv['observations'] or local['scene'] != cv['scene']):
            raise ValueError('Retrospective localization differs from original CV')
        raw_sources = {sha(path): path for path in Path(evaluations).glob('*.json')}
        if not e['hafnia']:
            raise ValueError('No persisted Hafnia assessments')
        if len(local['observations']) != len(cv['observations']):
            raise ValueError('Joined observations differ from detector source')
        known = {f['file']: f for f in m['frames']}
        frames, last = [], None
        for row, original in zip(local['observations'], cv['observations']):
            for key in ('file','timestamp_utc','sha256'):
                if row[key] != original[key]:
                    raise ValueError('Joined frame differs from CV source')
            if [o['box'] for o in row['objects']] != [o['box'] for o in original['objects']]:
                raise ValueError('Joined localization differs from CV source')
            now = seconds(row['timestamp_utc'])
            if not seconds(scene['start']) <= now < seconds(scene['end']) or last is not None and now <= last:
                raise ValueError('Unordered samples or interval mismatch')
            last = now
            path = (manifest.parent/row['file']).resolve()
            if not path.is_relative_to(manifest.parent) or row['file'] not in known:
                raise ValueError('Frame path outside original acquisition')
            if sha(path) != row['sha256'] or known[row['file']]['timestamp_utc'] != row['timestamp_utc']:
                raise ValueError('Original frame identity mismatch')
            frames.append(dict(path=str(path), sha256=row['sha256'], timestamp=row['timestamp_utc']))
        if not frames:
            raise ValueError('No persisted frames')
        expected = video_uri(m['camera_id'], *[datetime.fromisoformat(v.replace('Z','+00:00')) for v in e['interval_utc']])
        for h in e['hafnia']:
            if h['source_sha256'] not in raw_sources:
                raise ValueError('Original Hafnia source hash not found')
            raw_path = raw_sources[h['source_sha256']]
            raw = json.loads(raw_path.read_text(encoding='utf-8-sig'))
            if (raw['manifest_sha256'] != sha(manifest) or raw['request'] != h['request'] or
                    raw['summary']['Id'] != h['summary_id'] or raw['summary'].get('Response') != h['original_response'] or
                    raw['summary'].get('Request') != h['returned_request'] or parse_result(raw['summary']) != h['parsed']):
                raise ValueError('Joined Hafnia assessment differs from original source')
            if not historical:
                if spatial is None or json.loads(json.dumps(assemble(cv_path,manifest,raw_path,spatial))) != e:
                    raise ValueError('Fresh join requires exact source revalidation and spatial configuration')
            req, returned = h['request'], h['returned_request']
            extras = set(returned)-set(req)
            if (req['VideoUris'] != [expected] or any(returned.get(k) != v for k,v in req.items()) or
                    extras-{'AiModelId'} or 'AiModelId' in extras and returned['AiModelId'] != 'traffic-general'):
                raise ValueError('Saved Hafnia request identity mismatch')
        measurements = measure(local['observations'], **c['temporal_policy'])
        if measurements['qualifying_runs'] != e['measurements']['qualifying_runs']:
            raise ValueError('Configured temporal policy differs from saved measurements')
        identifier = sha(joined)[:24]
        runs = measurements['qualifying_runs']
        for i, frame in enumerate(frames):
            selected = measurements['trajectory'][i]['object']
            qualifies = any(seconds(r['first']) <= seconds(frame['timestamp']) <= seconds(r['last']) for r in runs)
            frame['box'] = selected['box'] if selected and qualifies else None
        document = dict(id=identifier, title='Potential sidewalk obstruction', capability=c['capability'],
            camera=c['name'], cameraGuid=c['camera_guid'], interval=e['interval_utc'],
            evidenceKind='saved_retrospective' if historical else 'fresh_analysis',
            status='Geometry review required' if not e.get('spatial',{}).get('approved') else 'Incident review required',
            operatorAction='Review pedestrian region and clearance',
            alarmStatus='unverified', frames=frames, runs=runs, hafnia=e['hafnia'],
            polygon=local['scene']['walkway'], geometryApproved=e.get('spatial',{}).get('approved') is True,
            manifestSha256=e['manifest_sha256'], cvSha256=e['cv_sha256'], joinedSha256=sha(joined),
            limitations=e['limitations'], annotations=None, dispatchReviewReady=False,
            provenance=dict(joined=str(joined),cv=str(cv_path),manifest=str(manifest)))
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO incidents VALUES (?,?)',(identifier,json.dumps(document)))
        return identifier

    def get(self, identifier):
        if not re.fullmatch('[a-f0-9]{24}', identifier):
            raise KeyError(identifier)
        row = self.db.execute('SELECT document FROM incidents WHERE id=?',(identifier,)).fetchone()
        if not row:
            raise KeyError(identifier)
        return json.loads(row[0])

    def index(self):
        records = []
        for (value,) in self.db.execute('SELECT document FROM incidents ORDER BY id'):
            d = json.loads(value)
            records.append({k:d[k] for k in ('id','title','camera','interval','evidenceKind','status','operatorAction','alarmStatus','runs')})
        return dict(records=records,cameras=[dict(id=c['camera_guid'],name=c['name'],configured=True,role=c['capability']) for c in cameras()],sources=['Persisted evidence index','Camera capability registry'])

    def public(self, identifier):
        d = self.get(identifier)
        d.pop('provenance')
        for i, frame in enumerate(d['frames']):
            frame.pop('path'); frame.pop('sha256')
            frame['file'] = f'/api/incidents/{identifier}/frames/{i}'
        return d


def handler(root, frontend=None):
    static = {}
    if frontend is not None:
        frontend = Path(frontend).resolve()
        for asset in frontend.rglob('*'):
            if asset.is_file() and asset.resolve().is_relative_to(frontend) and asset.suffix in {'.html','.js','.css','.woff','.woff2','.svg','.ico'}:
                static['/'+asset.relative_to(frontend).as_posix()] = asset
        if '/index.html' in static:
            static['/'] = static['/index.html']
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Reject DNS rebinding/cross-origin embedding; no CORS, cookies or writes.
            if self.headers.get('Host') not in {'127.0.0.1:8765','localhost:8765','127.0.0.1:4174','localhost:4174'}:
                self.send_error(403); return
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.send_error(403); return
            path = urlsplit(self.path).path
            store = EvidenceStore(root)
            try:
                if path == '/api/incidents':
                    data, mime = json.dumps(store.index()).encode(), 'application/json'
                elif match := re.fullmatch(r'/api/incidents/([a-f0-9]{24})(?:/frames/([0-9]+))?',path):
                    identifier, frame = match.groups()
                    if frame is None:
                        data, mime = json.dumps(store.public(identifier)).encode(), 'application/json'
                    else:
                        item = store.get(identifier)['frames'][int(frame)]
                        if sha(item['path']) != item['sha256']:
                            raise ValueError('Frame changed since indexing')
                        data, mime = Path(item['path']).read_bytes(), 'image/jpeg'
                elif path in static:
                    data = static[path].read_bytes()
                    mime = mimetypes.guess_type(str(static[path]))[0] or 'application/octet-stream'
                else:
                    self.send_error(404); return
                self.send_response(200)
                self.send_header('Content-Type',mime)
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Cross-Origin-Resource-Policy','same-origin')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers(); self.wfile.write(data)
            except (KeyError,IndexError,FileNotFoundError):
                self.send_error(404)
            except (ValueError,TypeError):
                self.send_error(409,'Evidence validation failed')
            finally:
                store.close()
        def do_POST(self):
            self.send_error(405,'Read-only evidence API')
    return Handler


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--root',type=Path,required=True,help='Private evidence index directory')
    sub=p.add_subparsers(dest='command',required=True)
    add=sub.add_parser('import')
    for name in ('joined','cv','manifest'):
        add.add_argument('--'+name,type=Path,required=True)
    add.add_argument('--evaluations',type=Path,required=True,help='Directory containing original saved Hafnia records')
    add.add_argument('--spatial',type=Path,help='Required camera-specific spatial configuration for fresh joins')
    serve = sub.add_parser('serve')
    serve.add_argument('--frontend',type=Path,help='Optional built frontend/dist; serves only frontend asset types')
    a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    if a.root.resolve().is_relative_to(repo) and not a.root.resolve().is_relative_to(repo/'runs'):
        p.error('Evidence index must be under ignored runs/ or outside repository')
    if a.command == 'import':
        store=EvidenceStore(a.root)
        try: print(store.register(a.joined,a.cv,a.manifest,a.evaluations,a.spatial))
        finally: store.close()
    else:
        print('Read-only evidence API: http://127.0.0.1:8765',flush=True)
        ThreadingHTTPServer(('127.0.0.1',8765),handler(a.root,a.frontend)).serve_forever()


if __name__ == '__main__':
    main()
