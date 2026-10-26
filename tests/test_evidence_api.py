"""Evidence API isolation and source validation; uses generated non-sensitive fixtures."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from adaptive_watch.evidence_api import EvidenceStore, handler
from adaptive_watch.incident import assemble
import test_sidewalk_incident


class EvidenceAPITests(unittest.TestCase):
    def register(self, directory, camera='escooter_left_across_sidewalk'):
        root=Path(directory); args=test_sidewalk_incident.IncidentTests().fixture(root,camera_name=camera)
        e=assemble(*args);joined=root/'joined.json';joined.write_text(json.dumps(e))
        store=EvidenceStore(root/'index')
        try:
            return store, store.register(joined,args[0],args[1],root,args[3]), args
        except Exception:
            store.close()
            raise

    def test_same_import_and_lookup_for_both_cameras(self):
        for camera in ('escooter_left_across_sidewalk','bin_pushed_over_onto_sidewalk'):
            with self.subTest(camera=camera),tempfile.TemporaryDirectory() as d:
                store,identifier,args=self.register(d,camera)
                try:
                    self.assertEqual(store.index()['records'][0]['id'],identifier)
                    record=store.public(identifier)
                    self.assertEqual(record['camera'],camera)
                    self.assertEqual(record['id'],identifier)
                    self.assertEqual(record['evidenceKind'],'fresh_analysis')
                    self.assertEqual(record['dispatchReviewReady'],assemble(*args)['dispatch_review_ready'])
                    self.assertEqual(record['alarmStatus'],'unverified')
                    self.assertNotIn('path',record['frames'][0])
                    self.assertNotIn('provenance',record)
                    with self.assertRaises(KeyError):store.get('../manifest.json')
                finally:store.close()

    def test_original_frame_tampering_rejected_at_import(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=test_sidewalk_incident.IncidentTests().fixture(root);e=assemble(*args)
            joined=root/'joined.json';joined.write_text(json.dumps(e));(root/'0.jpg').write_bytes(b'tamper')
            store=EvidenceStore(root/'index')
            try:
                with self.assertRaisesRegex(ValueError,'frame identity'):
                    store.register(joined,args[0],args[1],root,args[3])
            finally:store.close()

    def test_retrospective_import_never_promotes_to_fresh_or_alarm(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=test_sidewalk_incident.IncidentTests().fixture(root,normalized=True)
            e=assemble(*args)
            # Historic reports retain the original detector observation structure.
            cv=json.loads(args[0].read_text());cv['scene']['walkway_approved']=True
            args[0].write_text(json.dumps(cv))
            from adaptive_watch.incident import sha
            e=assemble(*args);e['schema_version']=1;e.pop('spatial')
            joined=root/'historic.json';joined.write_text(json.dumps(e))
            store=EvidenceStore(root/'index')
            try:
                identifier=store.register(joined,args[0],args[1],root)
                result=store.public(identifier)
                self.assertEqual(result['evidenceKind'],'saved_retrospective')
                self.assertFalse(result['dispatchReviewReady'])
                self.assertEqual(result['alarmStatus'],'unverified')
                self.assertFalse(result['geometryApproved'])
                e['hafnia'][0]['original_response']='fabricated text'
                joined.write_text(json.dumps(e))
                with self.assertRaisesRegex(ValueError,'differs from original source'):
                    store.register(joined,args[0],args[1],root)
            finally:store.close()

    def test_http_read_only_unknown_ids_host_and_frame_revalidation(self):
        with tempfile.TemporaryDirectory() as d:
            store,identifier,args=self.register(d);store.close()
            server=ThreadingHTTPServer(('127.0.0.1',0),handler(Path(d)/'index'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(path,method='GET',host='127.0.0.1:8765'):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                connection.request(method,path,headers={'Host':host})
                response=connection.getresponse();status=response.status;data=response.read();connection.close()
                return status,data
            try:
                self.assertEqual(request('/api/incidents')[0],200)
                self.assertEqual(request('/api/incidents',host='evil.example')[0],403)
                self.assertEqual(request('/api/incidents',method='POST')[0],405)
                self.assertEqual(request('/api/dispatch')[0],404)
                self.assertEqual(request('/api/incidents/'+'0'*24)[0],404)
                self.assertEqual(request(f'/api/incidents/{identifier}/frames/0')[0],200)
                (Path(d)/'0.jpg').write_bytes(b'changed')
                self.assertEqual(request(f'/api/incidents/{identifier}/frames/0')[0],409)
                self.assertEqual(request(f'/api/incidents/{identifier}/frames/999')[0],404)
            finally:server.shutdown();server.server_close();thread.join()

    def test_http_decisions_persist_and_reject_cross_origin(self):
        with tempfile.TemporaryDirectory() as d:
            store,identifier,_=self.register(d)
            evidence=sorted(o['observationId'] for o in store.get(identifier)['observations']);store.close()
            server=ThreadingHTTPServer(('127.0.0.1',0),handler(Path(d)/'index'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(origin, action='request_escalation', ids=evidence):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                body=json.dumps(dict(action=action,note='Reviewed',evidence=ids))
                connection.request('POST',f'/api/incidents/{identifier}/decisions',body,headers={'Host':'127.0.0.1:8765','Origin':origin,'Content-Type':'application/json'})
                response=connection.getresponse();status=response.status;data=response.read();connection.close();return status,data
            try:
                self.assertEqual(request('https://evil.example')[0],403)
                self.assertEqual(request('http://127.0.0.1:8765',ids=[])[0],409)
                status,data=request('http://127.0.0.1:8765');self.assertEqual(status,200)
                result=json.loads(data);self.assertEqual(result['state'],'review_required');self.assertEqual(len(result['approvalRequests']),1)
                self.assertEqual(result['alarmStatus'],'unverified')
                store=EvidenceStore(Path(d)/'index')
                try:self.assertEqual(len(store.get(identifier)['decisions']),1)
                finally:store.close()
            finally:server.shutdown();server.server_close();thread.join()
