import json
from pathlib import Path
import tempfile
import unittest

from adaptive_watch import native_review
from adaptive_watch.native_review import NativeReview
from scene_contracts import analytics_event
from scene_contracts.analytics_event import AnalyticsEventError

CASE = dict(
    interval=['2026-10-22T11:03:39Z', '2026-10-22T11:03:52Z'],
    hafnia=dict(summaryId='5a1ab040-fc44-4156-ad7a-1eeecd8c7b60'),
    vision=dict(trigger=dict(timestamp='2026-10-22T11:03:44.513Z', box=[0.4, 0.38, 0.6, 0.78])),
    handoff=dict(message='Review exception: Hafnia reported no entry.', camera='Station platform'),
)
GUID = '1DFB0898-730F-44C1-BCA8-7F541E8EF116'


class Reply:
    status, body = 200, b''
    def read(self, n): return self.body


class FakeConnection:
    sent = []
    def __init__(self, host, port, timeout=10): self.host, self.port = host, port
    def request(self, method, path, body=None, headers=None): FakeConnection.sent.append(body)
    def getresponse(self): return Reply()
    def close(self): pass


class NativeReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name)/'native').mkdir()
        FakeConnection.sent = []
        self.original = analytics_event.http.client.HTTPConnection
        analytics_event.http.client.HTTPConnection = FakeConnection
        analytics_event.send.__defaults__ = (False, 10.0, FakeConnection)

    def tearDown(self):
        analytics_event.send.__defaults__ = (False, 10.0, self.original)
        analytics_event.http.client.HTTPConnection = self.original
        self.tmp.cleanup()

    def test_preview_is_deterministic_and_uses_source_time_and_camera(self):
        n = NativeReview(self.tmp.name, '127.0.0.1:9090')
        a, b = n.preview(CASE, GUID), n.preview(CASE, GUID)
        self.assertEqual(a['sha256'], b['sha256'])
        self.assertIn('2026-10-22T11:03:44.513Z', a['xml'])
        self.assertIn('1dfb0898-730f-44c1-bca8-7f541e8ef116', a['xml'])
        self.assertIn(native_review.EVENT_NAME, a['xml'])
        self.assertNotIn('BoundingBox', a['xml'])
        self.assertIn('BoundingBox', n.preview(CASE, GUID, include_box=True)['xml'])

    def test_send_requires_enablement_and_exact_digest(self):
        n = NativeReview(self.tmp.name, '127.0.0.1:9090')
        with self.assertRaises(ValueError):
            n.send(CASE, 'railway', GUID, 'abc')
        n = NativeReview(self.tmp.name, '127.0.0.1:9090', enabled=True)
        with self.assertRaises(AnalyticsEventError):
            n.send(CASE, 'railway', GUID, 'deadbeefdeadbeef')
        self.assertEqual(FakeConnection.sent, [])

    def test_accepted_send_is_recorded_and_never_repeated(self):
        n = NativeReview(self.tmp.name, '127.0.0.1:9090', enabled=True)
        digest = n.preview(CASE, GUID)['sha256'][:16]
        row = n.send(CASE, 'railway', GUID, digest)
        self.assertEqual(row['state'], 'accepted')
        status = json.loads((Path(self.tmp.name)/'native/status.json').read_text())
        self.assertEqual(status['railway']['state'], 'sent')
        self.assertNotIn('alarmId', status['railway'])
        with self.assertRaises(AnalyticsEventError):
            n.send(CASE, 'railway', GUID, digest)
        self.assertEqual(len(FakeConnection.sent), 1)

    def test_unmatched_event_is_blocked_not_sent(self):
        Reply.body = b'Warning: Event message not known'
        try:
            n = NativeReview(self.tmp.name, '127.0.0.1:9090', enabled=True)
            n.send(CASE, 'railway', GUID, n.preview(CASE, GUID)['sha256'][:16])
            status = json.loads((Path(self.tmp.name)/'native/status.json').read_text())
            self.assertEqual(status['railway']['state'], 'blocked')
        finally:
            Reply.body = b''


if __name__ == '__main__':
    unittest.main()
