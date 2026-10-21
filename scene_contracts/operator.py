"""Durable, explicit operator actions; no automatic inference retries or native writes."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from uuid import uuid4

from scene26 import camera
from .contracts import load_contracts, make_contract, inference_request
from .gateway import Gateway, GatewayError, video_uri
from .store import interval


class Operator:
    def __init__(self, store, camera_map, contracts_dir):
        self.store = store
        self.camera_map = camera_map
        self.contracts_dir = contracts_dir

    def cameras(self):
        path = Path(self.camera_map)
        if not path.exists():
            return []
        rows = json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('Name'), str) for r in rows):
            raise ValueError('Invalid camera catalog')
        return sorted({r['Name'] for r in rows})

    def contracts(self):
        return load_contracts(self.contracts_dir) + [json.loads(r[0]) for r in self.store.db.execute('SELECT contract_json FROM operator_contracts ORDER BY rowid')]

    def create_contract(self, name, camera_name, condition):
        if camera_name not in self.cameras():
            raise ValueError('Select a camera from the verified catalog')
        contract = make_contract(name, camera_name, condition, 'custom-' + uuid4().hex)
        camera(SimpleNamespace(camera=camera_name, camera_map=self.camera_map, camera_id=None), contract)
        with self.store.db:
            self.store.db.execute('INSERT INTO operator_contracts VALUES (?,?)', (contract['id'], json.dumps(contract)))
        return contract

    def preview(self, contract_id, camera_name, start, end):
        contract = next((c for c in self.contracts() if c['id'] == contract_id), None)
        if contract is None:
            raise ValueError('Unknown contract')
        camera_id = camera(SimpleNamespace(camera=camera_name, camera_map=self.camera_map, camera_id=None), contract)
        start, end = interval(start, end)
        uri = video_uri(camera_id, datetime.fromisoformat(start.replace('Z', '+00:00')), datetime.fromisoformat(end.replace('Z', '+00:00')))
        metadata = {'contract': contract, 'camera_id': camera_id, 'camera_name': camera_name,
                    'start': start, 'end': end, 'payload': inference_request(contract, uri)}
        request_id = uuid4().hex
        with self.store.db:
            self.store.db.execute('INSERT INTO requests(id,status,metadata,created_at) VALUES (?,?,?,?)',
                                  (request_id, 'preview', json.dumps(metadata), datetime.now(timezone.utc).isoformat()))
        return request_id

    def request(self, request_id):
        row = self.store.db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown request')
        return {**dict(row), 'metadata': json.loads(row['metadata'])}

    def recent(self):
        return [dict(r) for r in self.store.db.execute('SELECT id,status,summary_id,created_at FROM requests ORDER BY rowid DESC LIMIT 30')]

    def claim(self, request_id, status, expected='preview'):
        with self.store.db:
            changed = self.store.db.execute('UPDATE requests SET status=? WHERE id=? AND status=?', (status, request_id, expected)).rowcount
        return changed == 1

    def update(self, request_id, status, summary_id=None, message=''):
        with self.store.db:
            self.store.db.execute('UPDATE requests SET status=?,summary_id=?,message=? WHERE id=?', (status, summary_id, message, request_id))

    def client(self):
        if not os.getenv('HAFNIA_GW_PASSWORD'):
            raise GatewayError('Set HAFNIA_GW_PASSWORD in the server process before live access')
        client = Gateway()
        client.authenticate()
        return client

    def submit(self, request_id):
        job = self.request(request_id)
        if not self.claim(request_id, 'submitting'):
            return
        try:
            item = self.client().request('POST', '/api/Summaries', job['metadata']['payload'])
            if not isinstance(item, dict) or not isinstance(item.get('Id'), str) or not item['Id'].strip():
                raise GatewayError('Missing summary identity')
            self.update(request_id, 'running', item['Id'])
            self.finish(request_id, item)
        except Exception:
            # A transport failure may follow an accepted POST; never retry it automatically.
            current = self.request(request_id)
            self.update(request_id, 'attention', current['summary_id'], 'Submission or storage failed. Check gateway History before doing anything else. Do not resubmit; recover the existing summary below.')

    def finish(self, request_id, item):
        job = self.request(request_id)
        m = job['metadata']
        if not isinstance(item, dict) or item.get('Id') != job['summary_id']:
            raise ValueError('Summary identity mismatch')
        if 'VideoUris' in item and item['VideoUris'] != m['payload']['VideoUris']:
            raise ValueError('Recording provenance mismatch')
        if item.get('Progress') not in {'Completed', 'Failed'}:
            return
        self.store.ingest(m['contract'], item, m['camera_id'], m['camera_name'], m['start'], m['end'])
        self.update(request_id, 'completed', item['Id'])

    def refresh(self, request_id):
        job = self.request(request_id)
        if job['summary_id'] and job['status'] != 'completed':
            try:
                item = self.client().request('GET', '/api/Summaries/' + quote(job['summary_id'], safe=''))
                self.finish(request_id, item)
                if self.request(request_id)['status'] != 'completed':
                    self.update(request_id, 'running', job['summary_id'], 'Gateway is processing this recorded interval.')
            except Exception:
                if self.request(request_id)['status'] != 'completed':
                    self.update(request_id, 'attention', job['summary_id'], 'Result fetch failed. Existing evidence remains available. Refresh this summary later; no inference was resubmitted.')

    def import_result(self, request_id, item):
        job = self.request(request_id)
        if job['status'] not in {'preview', 'attention', 'running'}:
            raise ValueError('Request is already complete or an action is in progress; use CLI ingest for interrupted submissions')
        if not isinstance(item, dict):
            raise ValueError('Result must be a JSON object')
        if 'result' in item:
            m = job['metadata']
            if any(item.get(k) != m[k] for k in ('contract', 'camera_id', 'camera_name', 'start', 'end')):
                raise ValueError('Manifest provenance mismatch')
            item = item['result']
        if not isinstance(item, dict) or item.get('Progress') not in {'Completed', 'Failed'} or not isinstance(item.get('Id'), str) or not item['Id'].strip():
            raise ValueError('Import requires a terminal result with a summary ID')
        if job['summary_id'] and item['Id'] != job['summary_id']:
            raise ValueError('Recovery must match the submitted summary ID')
        m = job['metadata']
        if 'VideoUris' in item and item['VideoUris'] != m['payload']['VideoUris']:
            raise ValueError('Recording provenance mismatch')
        if not self.claim(request_id, 'importing', job['status']):
            raise ValueError('Another action already claimed this request')
        try:
            self.store.ingest(m['contract'], item, m['camera_id'], m['camera_name'], m['start'], m['end'])
            self.update(request_id, 'completed', item['Id'])
        except Exception:
            self.update(request_id, job['status'], job['summary_id'], job['message'])
            raise
