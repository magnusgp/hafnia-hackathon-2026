from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import scene26
from scene_contracts import analytics_event as ae
from scene_contracts.store import Store

FIXTURES = Path(__file__).parent / 'fixtures'
CAMERA = '00000000-0000-0000-0000-000000000001'
MESSAGE = 'H26 Visually Observed Damage'


def golden_event(**extra):
    key = ae.dispatch_key('summary-fixture-1', 'scene-property-damage', MESSAGE)
    return key, ae.build(MESSAGE, CAMERA, '2026-10-19T12:00:00Z', key,
                         description='Property integrity (SC_BREACH). OBSERVATIONS: A person strikes the window; '
                                     'VISIBLE_EVIDENCE: Crack appears. Operator verification required.',
                         start='2026-10-19T12:00:00Z', end='2026-10-19T12:00:15Z',
                         boxes=[{'top': 0.2, 'left': 0.4, 'bottom': 0.9, 'right': 0.6}], **extra)


class FakeConnection:
    """Records requests; replies with a scripted (status, body) or raises."""
    calls = []
    reply = (200, '')

    def __init__(self, host, port, timeout):
        self.target = (host, port, timeout)

    def request(self, method, path, body, headers):
        FakeConnection.calls.append((self.target, method, path, body, headers))
        if isinstance(FakeConnection.reply, Exception):
            raise FakeConnection.reply

    def getresponse(self):
        status, body = FakeConnection.reply

        class R:
            def __init__(self):
                self.status = status

            def read(self, n):
                return body.encode()
        return R()

    def close(self):
        pass


class SerializerTests(unittest.TestCase):
    def test_golden_fixture_is_byte_identical(self):
        self.assertEqual(golden_event()[1], (FIXTURES / 'analytics-event-golden.xml').read_bytes())

    @unittest.skipUnless(importlib.util.find_spec('lxml'), 'install lxml to validate against the Milestone XSD')
    def test_valid_against_milestone_xsd(self):
        from lxml import etree

        schema = etree.XMLSchema(etree.parse(str(FIXTURES / 'AnalyticsEvent.xsd')))
        for data in (golden_event()[1], golden_event(server_id='beef2f96-03db-4815-a33c-adcc9fcb8610')[1]):
            self.assertTrue(schema.validate(etree.fromstring(data)), schema.error_log)

    def test_full_server_id_block_precedes_object_id_in_schema_order(self):
        mgmt = '9d4de506-9b54-4d03-b852-0a4b0fd79958'
        data = golden_event(server_id=dict(type='XPCO', hostname='p022', port=80, id=mgmt))[1].decode()
        self.assertIn(f'<FQID><ServerId><Type>XPCO</Type><Hostname>p022</Hostname><Port>80</Port><Id>{mgmt}</Id></ServerId>'
                      f'<ObjectId>{CAMERA}</ObjectId>', data)
        self.assertTrue(ae.validate(data.encode()))
        with self.assertRaises(ValueError):
            golden_event(server_id=dict(type='XPCO', id='not-a-guid'))

    def test_message_and_camera_identity_are_exact(self):
        data = golden_event()[1].decode()
        self.assertIn(f'<Message>{MESSAGE}</Message>', data)
        self.assertIn(f'<ObjectId>{CAMERA}</ObjectId><Kind>{ae.CAMERA_KIND}</Kind>', data)
        self.assertIn(f'<ID>{ae.ZERO_GUID}</ID>', data)
        with self.assertRaises(ValueError):
            ae.build(MESSAGE + ' ', CAMERA, '2026-10-19T12:00:00Z', 'k')
        with self.assertRaises(ValueError):
            ae.build(MESSAGE, 'not-a-guid', '2026-10-19T12:00:00Z', 'k')
        with self.assertRaises(ValueError):
            ae.build(MESSAGE, CAMERA, '2026-10-19T12:00:00', 'k')  # naive time

    def test_local_offsets_become_utc(self):
        data = ae.build(MESSAGE, CAMERA, '2026-10-19T14:00:00+02:00', 'k').decode()
        self.assertIn('<Timestamp>2026-10-19T12:00:00.000Z</Timestamp>', data)

    def test_validator_rejects_schema_violations(self):
        good = golden_event()[1].decode()
        bad = [
            good.replace('urn:milestone-systems', 'urn:other'),
            good.replace('<Message>H26 Visually Observed Damage</Message>', ''),
            good.replace('<Type>Scene Contracts evidence</Type><Message>H26 Visually Observed Damage</Message>',
                         '<Message>H26 Visually Observed Damage</Message><Type>Scene Contracts evidence</Type>'),
            good.replace(CAMERA, '1234'),
            good.replace('<Bottom>0.9</Bottom>', '<Bottom>1.4</Bottom>'),
            good.replace('<Top>0.2</Top>', '<Top>0.95</Top>'),
            good.replace('2026-10-19T12:00:15.000Z', 'yesterday'),
            good.replace('<Vendor>', '<Unknown/><Vendor>'),
            good[:-10],
        ]
        for text in bad:
            with self.assertRaises(ae.AnalyticsEventError, msg=text[:80]):
                ae.validate(text.encode())

    def test_event_map_resolution_is_exact(self):
        m = ae.load_event_map()
        self.assertEqual(ae.resolve_message(m, 'scene-property-damage', 'positive'), MESSAGE)
        for contract, outcome in (('scene-property-damage', 'uncertain'), ('roadway-visibility', 'positive')):
            with self.assertRaises(ae.AnalyticsEventError):
                ae.resolve_message(m, contract, outcome)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = ae.Ledger(Path(self.tmp.name) / 'db.sqlite3')
        self.key, self.data = golden_event()
        self.approval = hashlib.sha256(self.data).hexdigest()[:12]
        FakeConnection.calls, FakeConnection.reply = [], (200, '')

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def send(self, **kw):
        return ae.send(self.ledger, self.key, self.data, '127.0.0.1:9090', kw.pop('approval', self.approval),
                       connection=FakeConnection, **kw)

    def test_classification_follows_documented_responses(self):
        self.assertEqual(ae.classify(200, ''), 'accepted')
        self.assertEqual(ae.classify(200, 'Warning: Device not known'), 'rejected_warning')
        self.assertEqual(ae.classify(200, 'Warning: Event message not known'), 'rejected_warning')
        self.assertEqual(ae.classify(400, 'SerializationException'), 'rejected_http')
        self.assertEqual(ae.classify(403, ''), 'rejected_http')
        self.assertEqual(ae.classify(500, 'starting'), 'uncertain')

    def test_wrong_approval_sends_and_records_nothing(self):
        for approval in (None, '', self.approval[:8], '0' * 12):
            with self.assertRaises(ae.AnalyticsEventError):
                self.send(approval=approval)
        self.assertEqual((FakeConnection.calls, self.ledger.attempts(self.key)), ([], []))

    def test_single_post_with_content_length_and_duplicate_refused(self):
        row = self.send()
        self.assertEqual((row['state'], row['attempt'], row['http_status']), ('accepted', 1, 200))
        (_, port, _), method, path, body, headers = FakeConnection.calls[0]
        self.assertEqual((port, method, path, body), (9090, 'POST', '/', self.data))
        self.assertEqual(headers, {'Content-Type': 'text/xml', 'Content-Length': str(len(self.data))})
        for reattempt in (False, True):
            with self.assertRaises(ae.AnalyticsEventError):
                self.send(reattempt=reattempt)
        self.assertEqual(len(FakeConnection.calls), 1)

    def test_warning_is_not_delivery_and_needs_explicit_reattempt(self):
        FakeConnection.reply = (200, 'Warning: Device not known')
        self.assertEqual(self.send()['state'], 'rejected_warning')
        with self.assertRaises(ae.AnalyticsEventError):
            self.send()
        FakeConnection.reply = (200, '')
        self.assertEqual(self.send(reattempt=True)['attempt'], 2)

    def test_uncertain_outcome_blocks_until_reconciled(self):
        FakeConnection.reply = socket.timeout('timed out')
        self.assertEqual(self.send()['state'], 'uncertain')
        for reattempt in (False, True):
            with self.assertRaises(ae.AnalyticsEventError):
                self.send(reattempt=reattempt)
        self.assertEqual(len(FakeConnection.calls), 1)
        with self.assertRaises(ValueError):
            self.ledger.reconcile(self.key, False, ' ')
        self.ledger.reconcile(self.key, False, 'No alarm in Smart Client; Event Server log shows no receipt')
        FakeConnection.reply = (200, '')
        self.assertEqual(self.send(reattempt=True)['state'], 'accepted')

    def test_claim_persists_across_processes(self):
        FakeConnection.reply = socket.timeout('timed out')
        self.send()
        self.ledger.close()
        self.ledger = ae.Ledger(Path(self.tmp.name) / 'db.sqlite3')
        with self.assertRaises(ae.AnalyticsEventError):
            self.send(reattempt=True)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'db.sqlite3')
        self.map = Path(self.tmp.name) / 'cameras.local.json'
        self.map.write_text(json.dumps([{'Name': 'vandalism', 'Id': CAMERA}]))

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), patch('http.client.HTTPConnection', side_effect=AssertionError('network')):
            code = scene26.run(scene26.parser().parse_args(['--db', self.db, 'analytics-event', *argv]))
        return code, out.getvalue()

    def test_manual_test_preview_is_dry_run_and_deterministic(self):
        argv = ['preview', '--manual-test', '--test-id', 't1', '--message', MESSAGE, '--camera', 'vandalism',
                '--camera-map', str(self.map), '--at', '2026-10-21T12:00:00Z']
        _, first = self.cli(*argv)
        _, second = self.cli(*argv)
        self.assertEqual(first, second)
        self.assertIn('DRY RUN: nothing was sent', first)
        self.assertIn(f'<ObjectId>{CAMERA}</ObjectId>', first)
        ledger = ae.Ledger(self.db)
        self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM analytics_dispatches').fetchone()[0], 0)
        ledger.close()

    def test_only_positive_ingested_observations_map_to_events(self):
        from tests.test_scenes import fixture
        from scene_contracts.contracts import load_contracts

        contract = next(c for c in load_contracts() if c['id'] == 'property-damage')
        store = Store(self.db)
        for kind, start in (('positive', '2026-10-19T12:00:00Z'), ('negative', '2026-10-19T12:01:00Z')):
            item = {**fixture(kind), 'Id': f'sid-{kind}'}
            store.ingest(contract, item, CAMERA, 'vandalism', start, start.replace(':00Z', ':15Z'))
        store.close()
        _, out = self.cli('preview', '--summary-id', 'sid-positive')
        self.assertIn(f'<Message>{MESSAGE}</Message>', out)
        self.assertIn('<StartTime>2026-10-19T12:00:00.000Z</StartTime>', out)
        with self.assertRaises(ValueError):
            self.cli('preview', '--summary-id', 'sid-negative')
        with self.assertRaises(ValueError):
            self.cli('preview', '--summary-id', 'unknown')


if __name__ == '__main__':
    unittest.main()
