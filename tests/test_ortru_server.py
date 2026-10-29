"""Ortru HTTP contract: envelope, same-origin and CSRF, Watch lifecycle, decision persistence, native preview/send with a fake transport."""
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from ortru.engine import Engine
from ortru.native import Native
from ortru.server import App, serve
from ortru.watches import Watches
from tests.test_ortru import CATALOG, DEST, GUID, GUID2, REGION, FakeConnection, FakeGateway, FakeRunner, config

BOX = dict(polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]])


class Client:
    def __init__(self, port):
        self.port, self.cookie, self.csrf = port, '', ''

    def call(self, method, path, body=None, headers=None):
        c = HTTPConnection('127.0.0.1', self.port, timeout=30)
        h = {'Cookie': self.cookie, 'X-Ortru-CSRF': self.csrf}
        h.update(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h['Content-Type'] = 'application/json'
        c.request(method, path, data, h)
        r = c.getresponse()
        raw = r.read()
        sc = r.getheader('Set-Cookie')
        if sc:
            self.cookie = sc.split(';')[0]
        c.close()
        try:
            j = json.loads(raw)
            self.csrf = j.get('csrf') or self.csrf
            return r.status, j
        except ValueError:
            return r.status, raw


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.watches = Watches(root/'ortru.sqlite3', CATALOG, DEST)
        self.runner = FakeRunner()
        self.engine = Engine(root, self.watches, self.runner, gateway_factory=lambda: FakeGateway())
        FakeConnection.sent = []
        self.native = Native(root/'ledger.sqlite3', '127.0.0.1:9090', True, root/'status.json', DEST, connection=FakeConnection)
        (root/'fe').mkdir()
        (root/'fe/index.html').write_text('<html>ortru</html>')
        self.app = App(root, root, root/'fe', self.engine, self.watches, self.native, None, CATALOG, self.runner, True, True)
        self.server = serve(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.c = Client(self.server.server_port)
        self.c.call('GET', '/api/ortru')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        for t in list(self.engine.threads.values()):
            t.join(10)
        self.temp.cleanup()

    def run_watch(self, **over):
        st, w = self.c.call('POST', '/api/watches', config(**over))
        self.assertEqual(st, 200, w)
        wid = w['data']['id']
        self.assertEqual(self.c.call('POST', f'/api/watches/{wid}/status', dict(status='active', baseVersion=1))[0], 200)
        st, j = self.c.call('POST', f'/api/watches/{wid}/run', {})
        self.assertEqual(st, 200, j)
        job = j['data']['job']['id']
        self.engine.wait(job)
        return wid, job

    def test_envelope_bootstrap_and_security(self):
        st, j = self.c.call('GET', '/api/ortru')
        self.assertEqual((st, j['schema'], j['ok']), (200, 'ortru.v1', True))
        self.assertEqual({c['id'] for c in j['data']['capabilities'] if c['available']}, {'person_region_proximity'})
        self.assertEqual(len(j['data']['cameras']), 2)
        self.assertEqual(self.c.call('GET', '/api/ortru', headers=dict(Host='evil.example'))[0], 403)
        self.assertEqual(self.c.call('GET', '/api/ortru', headers={'Origin': 'http://evil.example'})[0], 403)
        st, j = self.c.call('POST', '/api/watches', config(), headers={'X-Ortru-CSRF': 'wrong'})
        self.assertEqual(st, 403)
        self.assertNotIn(b'password', json.dumps(j).encode().lower())

    def test_error_envelope_is_uniform(self):
        st, j = self.c.call('POST', '/api/watches', config(name=''))
        self.assertEqual((st, j['ok'], j['data']), (422, False, None))
        self.assertIn('name', j['error']['message'])
        st, j = self.c.call('GET', '/api/watches/w-nope')
        self.assertEqual((st, j['ok']), (404, False))

    def test_full_operator_flow_with_fake_transport(self):
        wid, job = self.run_watch()
        st, q = self.c.call('GET', '/api/queue')
        self.assertEqual([e['id'] for e in q['data']['live']], [job])
        e = self.c.call('GET', f'/api/exceptions/{job}')[1]['data']
        self.assertEqual((e['schema'], e['decision']['status'], e['native']['state']), ('ortru.v1', 'undecided', 'ready'))
        self.assertEqual(self.c.call('GET', f'/api/exceptions/{job}/frames/0')[0], 200)
        self.assertEqual(self.c.call('GET', f'/api/exceptions/{job}/video')[0], 200)
        st, j = self.c.call('POST', f'/api/exceptions/{job}/native', dict(action='send', confirmed=True, approval='a'*12))
        self.assertEqual(st, 422)  # no saved decision yet
        dec = dict(expectedRevision=0, verdict='visible', note='Person on track bed', watchedFootage=True, outcome='escalate')
        st, j = self.c.call('POST', f'/api/exceptions/{job}/decision', dec)
        self.assertEqual((st, j['data']['decision']['revision'], j['data']['decision']['status']), (200, 1, 'review_requested'))
        self.assertEqual(self.c.call('POST', f'/api/exceptions/{job}/decision', dec)[0], 409)  # stale revision
        st, p = self.c.call('POST', f'/api/exceptions/{job}/native', dict(action='preview'))
        sha = p['data']['preview']['sha256']
        self.assertIn('AnalyticsEvent', p['data']['preview']['xml'])
        self.assertEqual(FakeConnection.sent, [])
        st, j = self.c.call('POST', f'/api/exceptions/{job}/native', dict(action='send', confirmed=False, approval=sha[:16]))
        self.assertEqual(st, 422)
        st, j = self.c.call('POST', f'/api/exceptions/{job}/native', dict(action='send', confirmed=True, approval=sha[:16]))
        self.assertEqual(st, 200, j)
        n = j['data']['exception']['native']
        self.assertEqual((n['state'], n['transport']['state'], n['smartClient']), ('sent', 'accepted', 'not_verified'))
        st, j = self.c.call('POST', f'/api/exceptions/{job}/native', dict(action='send', confirmed=True, approval=sha[:16]))
        self.assertEqual(st, 422)
        self.assertEqual(len(FakeConnection.sent), 1)
        again = self.c.call('GET', f'/api/exceptions/{job}')[1]['data']
        self.assertEqual((again['decision']['note'], again['native']['state']), ('Person on track bed', 'sent'))

    def test_watch_lifecycle_snapshot_and_conflict(self):
        st, w = self.c.call('POST', '/api/watches', config(cameraId=GUID2))
        wid = w['data']['id']
        self.assertEqual(w['data']['status'], 'draft')
        self.assertIn('No XProtect alarm', w['data']['problems'][0]['text'])
        self.assertEqual(self.c.call('POST', f'/api/watches/{wid}/snapshot', {})[0], 200)
        self.assertEqual(self.c.call('GET', f'/api/watches/{wid}/snapshot')[0], 200)
        st, w2 = self.c.call('PUT', f'/api/watches/{wid}', dict(baseVersion=1, config=config(cameraId=GUID2, name='Wall v2')))
        self.assertEqual(w2['data']['version'], 2)
        st, j = self.c.call('PUT', f'/api/watches/{wid}', dict(baseVersion=1, config=config(cameraId=GUID2, name='Late')))
        self.assertEqual((st, j['error']['code']), (409, 'stale_version'))
        for s in ('active', 'paused', 'disabled'):
            self.assertEqual(self.c.call('POST', f'/api/watches/{wid}/status', dict(status=s))[1]['data']['status'], s)
        st, j = self.c.call('POST', f'/api/watches/{wid}/run', {})
        self.assertEqual(st, 422)
        self.assertIn('disabled', j['error']['message'])

    def test_unsupported_detector_rejected_before_activation(self):
        st, j = self.c.call('POST', '/api/watches', config(detector=dict(id='object_stationarity')))
        self.assertEqual(st, 422)
        self.assertIn('not available', j['error']['message'])

    def test_no_native_for_unconfigured_camera_but_review_works(self):
        wid, job = self.run_watch(cameraId=GUID2, region=BOX)
        e = self.c.call('GET', f'/api/exceptions/{job}')[1]['data']
        self.assertEqual(e['native']['state'], 'not_configured')
        st, j = self.c.call('POST', f'/api/exceptions/{job}/decision', dict(expectedRevision=0, verdict='visible', note='x', watchedFootage=True, outcome='escalate'))
        self.assertEqual(st, 422)
        st, j = self.c.call('POST', f'/api/exceptions/{job}/decision', dict(expectedRevision=0, verdict='visible', note='Seen', watchedFootage=True, outcome='confirm_local'))
        self.assertEqual((st, j['data']['decision']['status']), (200, 'confirmed'))
        self.assertEqual(FakeConnection.sent, [])

    def test_decision_does_not_leak_across_exceptions(self):
        wid, a = self.run_watch()
        self.c.call('POST', f'/api/exceptions/{a}/decision', dict(expectedRevision=0, verdict='unclear', note='', watchedFootage=True, outcome='dismiss'))
        wid2, b = self.run_watch(name='Another', cameraId=GUID2, region=BOX)
        self.assertEqual(self.c.call('GET', f'/api/exceptions/{b}')[1]['data']['decision']['status'], 'undecided')
        self.assertEqual(self.c.call('GET', f'/api/exceptions/{a}')[1]['data']['decision']['status'], 'dismissed')


if __name__ == '__main__':
    unittest.main()
