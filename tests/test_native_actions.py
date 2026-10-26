import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from adaptive_watch import episodes
from adaptive_watch.evidence_api import EvidenceStore
from adaptive_watch.incident import assemble, proposal, sha
from adaptive_watch.native_actions import NativeActions
from scene_contracts.analytics_event import Ledger
import test_sidewalk_incident


class NativeActionTests(unittest.TestCase):
    def fixture(self, root):
        args = test_sidewalk_incident.IncidentTests().fixture(root)
        e = assemble(*args)
        clip = root / 'acquisition/clip'
        clip.mkdir(parents=True)
        for frame in root.glob('*.jpg'):
            shutil.copyfile(frame, clip / frame.name)
        shutil.copyfile(args[1], clip / 'manifest.json')
        shutil.copyfile(args[0], root / (e['camera_name'] + '.json'))
        raw = root / 'hafnia'
        raw.mkdir()
        shutil.copyfile(args[2], raw / 'record.json')
        joined = root / 'joined.json'
        joined.write_text(json.dumps(e))
        payload, meta = proposal(e)
        meta['evidence_sha256'] = sha(joined)
        (root / 'proposal.xml').write_bytes(payload)
        (root / 'proposal.json').write_text(json.dumps(meta))
        Ledger(root / 'ledger.sqlite3').close()
        store = EvidenceStore(root / 'index')
        identifier = store.register(joined, args[0], args[1], raw, args[3])
        ids = sorted(o['observationId'] for o in store.get(identifier)['observations'])
        episodes.decide(store.db, identifier, 'request_escalation', evidence=ids)
        config = dict(configured=True, configuration_verified_by='test administrator',
                      configuration_verified_at='2026-10-26T10:00:00Z',
                      event_name='Adaptive Watch Sidewalk Obstruction', destination_label='XProtect test destination',
                      target='127.0.0.1:9090', ledger=str(root / 'ledger.sqlite3'),
                      incidents={e['camera_guid']:dict(root=str(root), spatial=str(args[3]))})
        path = root / 'native.local.json'
        path.write_text(json.dumps(config))
        return store, identifier, NativeActions(path)

    def test_human_confirmation_session_destination_and_single_send(self):
        with tempfile.TemporaryDirectory() as directory:
            store, identifier, native = self.fixture(Path(directory))
            try:
                with patch('adaptive_watch.dispatch.send', return_value=dict(state='accepted')) as send:
                    preview = native.prepare(store, identifier, 'human-session')
                    send.assert_not_called()
                    self.assertNotIn('xml', preview)
                    self.assertNotIn('target', preview)
                    self.assertNotIn('payload', preview)
                    for session, confirmed in [('other-session', True), ('human-session', False)]:
                        with self.assertRaises(ValueError):
                            native.confirm(store, identifier, session, dict(token=preview['token'], confirmed=confirmed))
                    result = native.confirm(store, identifier, 'human-session', dict(token=preview['token'], confirmed=True))
                    self.assertEqual(result['state'], 'accepted')
                    self.assertIn('verify alarm', result['reason'])
                    self.assertEqual(send.call_count, 1)
                    with self.assertRaises(ValueError):
                        native.confirm(store, identifier, 'human-session', dict(token=preview['token'], confirmed=True))
                    self.assertEqual(send.call_count, 1)
            finally:
                store.close()

    def test_changed_destination_or_expiry_cannot_send(self):
        with tempfile.TemporaryDirectory() as directory:
            store, identifier, native = self.fixture(Path(directory))
            try:
                preview = native.prepare(store, identifier, 'human-session')
                config = json.loads(native.config.read_text())
                config['target'] = '127.0.0.1:9999'
                native.config.write_text(json.dumps(config))
                with patch('adaptive_watch.dispatch.send') as send:
                    with self.assertRaisesRegex(ValueError, 'changed'):
                        native.confirm(store, identifier, 'human-session', dict(token=preview['token'], confirmed=True))
                    preview = native.prepare(store, identifier, 'human-session')
                    row = store.db.execute('SELECT token,document FROM native_confirmations WHERE token=?', (episodes.digest(preview['token']),)).fetchone()
                    expired = json.loads(row[1]); expired['expires'] = '2000-01-01T00:00:00+00:00'
                    with store.db:
                        store.db.execute('UPDATE native_confirmations SET document=? WHERE token=?', (json.dumps(expired), row[0]))
                    with self.assertRaisesRegex(ValueError, 'expired'):
                        native.confirm(store, identifier, 'human-session', dict(token=preview['token'], confirmed=True))
                    send.assert_not_called()
            finally:
                store.close()

    def test_uncertain_send_is_durable_and_blocks_retry_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            store, identifier, native = self.fixture(Path(directory))
            try:
                preview = native.prepare(store, identifier, 'human-session')
                with patch('adaptive_watch.dispatch.send', return_value=dict(state='uncertain')) as send:
                    result = native.confirm(store, identifier, 'human-session', dict(token=preview['token'], confirmed=True))
                    self.assertEqual(result['state'], 'uncertain')
                    with self.assertRaises(ValueError):
                        native.prepare(store, identifier, 'human-session')
                    ids = sorted(o['observationId'] for o in store.get(identifier)['observations'])
                    with self.assertRaisesRegex(ValueError, 'reserved'):
                        episodes.decide(store.db, identifier, 'dismiss', evidence=ids)
                    self.assertEqual(send.call_count, 1)
                path = store.root
                store.close()
                store = EvidenceStore(path)
                self.assertEqual(native.status(store, identifier)['state'], 'uncertain')
            finally:
                store.close()
