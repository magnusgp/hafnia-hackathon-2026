"""Integrity, temporal alignment and human decision gates for the saved-case workflow."""
import copy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from adaptive_watch.negative_review import Conflict, ReviewStore, digest, distance, sha, validate_region
from adaptive_watch.negative_review_api import handler


class ReviewFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        original = self.root/'frame.jpg'
        original.write_bytes(b'original evidence')
        self.record = dict(id='railway-negative-review',camera='railway',cameraGuid='camera',interval=['start','end'],
            frames=[dict(index=0,timestamp='2026-10-22T11:03:44.513Z',mediaTime=0,box=[.5,.2,.7,.8],path=str(original))],
            cv=dict(trackId=7,zone=dict(polygon=[[.25,.32],[1,.67],[1,1],[.62,1]])),
            hafnia=dict(outcome='not_observed',summaryId='original-id',originalResponse='unchanged'),
            media=dict(path=str(original)),reference=dict(provenance='AI review'),diagnostic=dict(completed=24),
            native=dict(configured=False,dispatchAvailable=False),sources=[dict(path=str(original),sha256=sha(original))])
        self.store = ReviewStore(self.root)
        self.store.install(self.record)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def action(self,action,**kwargs):
        return self.store.act(dict(action=action,revision=self.store.view()['revision'],**kwargs))


class ReviewTests(ReviewFixture):
    def test_proximity_is_image_distance_not_entry(self):
        view = self.store.view()
        self.assertIsNone(view['state']['humanAnnotation'])
        self.assertIn('does not confirm entry',view['reason'])
        self.assertEqual(view['hafnia'],self.record['hafnia'])
        self.assertEqual(distance([.1,.1],[[0,0],[1,0],[1,1],[0,1]]),0)
        self.assertAlmostEqual(distance([2,.5],[[0,0],[1,0],[1,1],[0,1]]),1)

    def test_decision_requires_review_and_explicit_attestation(self):
        with self.assertRaisesRegex(ValueError,'Review footage'):
            self.action('dismiss',footageReviewed=True)
        self.action('review')
        with self.assertRaisesRegex(ValueError,'Confirm that'):
            self.action('dismiss')
        with self.assertRaisesRegex(ValueError,'Add a note'):
            self.action('dismiss',footageReviewed=True,annotation='entry_visible')
        v=self.action('request_xprotect_review',footageReviewed=True,annotation='uncertain',note='Seated contact is occluded.')
        self.assertEqual(v['state']['status'],'xprotect_review_requested')
        self.assertEqual(v['state']['humanAnnotation']['value'],'uncertain')
        self.assertEqual(v['hafnia'],self.record['hafnia'])
        self.assertFalse(v['native']['dispatchAvailable'])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM review_audit').fetchone()[0],2)
        self.store.close();self.store=ReviewStore(self.root)
        self.assertEqual(self.store.view()['state']['status'],'xprotect_review_requested')

    def test_stale_and_duplicate_decisions_are_rejected(self):
        revision=self.store.view()['revision']
        self.action('review')
        with self.assertRaises(Conflict):
            self.store.act(dict(action='dismiss',revision=revision,footageReviewed=True))
        saved=self.action('dismiss',footageReviewed=True)
        with self.assertRaisesRegex(ValueError,'Review footage'):
            self.store.act(dict(action='dismiss',revision=saved['revision'],footageReviewed=True))

    def test_source_and_record_tampering_block_read_and_decision(self):
        revision=self.store.view()['revision']
        Path(self.record['sources'][0]['path']).write_bytes(b'changed')
        with self.assertRaises(Conflict):self.store.view()
        with self.assertRaises(Conflict):self.store.act(dict(action='review',revision=revision))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM review_audit').fetchone()[0],0)

    def test_record_digest_is_verified(self):
        changed=copy.deepcopy(self.record);changed['hafnia']['outcome']='supported'
        self.store.db.execute('UPDATE review SET record=?',(json.dumps(changed),));self.store.db.commit()
        with self.assertRaisesRegex(Conflict,'record integrity'):self.store.view()

    def test_region_change_invalidates_review_without_modifying_original(self):
        self.action('review')
        view=self.action('configure_region',region=dict(polygon=[[0,0],[.1,0],[.1,.1],[0,.1]],threshold=0))
        self.assertFalse(view['state']['reviewed']);self.assertIsNone(view['trigger'])
        self.assertEqual(self.store.verified()[0],self.record)
        self.action('review')
        with self.assertRaisesRegex(ValueError,'condition is absent'):
            self.action('request_xprotect_review',footageReviewed=True)

    def test_invalid_regions_and_native_action_fail_closed(self):
        for polygon in ([[0,0],[1,0]],[[0,0],[1,1],[1,1]],[[0,0],[2,0],[1,1]]):
            with self.assertRaises(ValueError):validate_region(dict(polygon=polygon,threshold=0))
        with self.assertRaises(ValueError):validate_region(dict(polygon=[[0,0],[1,0],[0,1]],threshold=float('nan')))
        with self.assertRaisesRegex(ValueError,'native dispatch is unavailable'):self.action('send_native_event')


class HttpTests(ReviewFixture):
    def setUp(self):
        super().setUp()
        (self.root/'index.html').write_text('review')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.root,self.root))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        super().tearDown()

    def test_http_csrf_range_integrity_and_no_native_routes(self):
        with urlopen(self.base+'/api/review') as response:
            data=json.load(response);cookie=response.headers['Set-Cookie'].split(';')[0]
        with urlopen(Request(self.base+'/api/review',headers={'Cookie':cookie})) as response:
            self.assertEqual(json.load(response)['csrf'],data['csrf'])
        payload=json.dumps(dict(action='review',revision=data['review']['revision'])).encode()
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/review/action',data=payload,headers={'Content-Type':'application/json'}))
        self.assertEqual(error.exception.code,403)
        headers={'Content-Type':'application/json','Cookie':cookie,'X-Review-CSRF':data['csrf']}
        with urlopen(Request(self.base+'/api/review/action',data=payload,headers=headers)) as response:
            self.assertEqual(json.load(response)['review']['state']['status'],'reviewing')
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/review/action',data=payload,headers=headers))
        self.assertEqual(error.exception.code,409)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/review/native/confirm',data=b'{}',headers=headers))
        self.assertEqual(error.exception.code,403)
        with urlopen(Request(self.base+'/api/review/video',headers={'Range':'bytes=0-7'})) as response:
            self.assertEqual(response.status,206);self.assertEqual(response.read(),b'original')
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/review',headers={'Origin':'https://elsewhere.example'}))
        self.assertEqual(error.exception.code,403)
        Path(self.record['sources'][0]['path']).write_bytes(b'changed')
        with self.assertRaises(HTTPError) as error:urlopen(self.base+'/api/review/video')
        self.assertEqual(error.exception.code,409)


if __name__ == '__main__':unittest.main()
