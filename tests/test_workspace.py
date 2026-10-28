"""Case isolation, source failures, optimistic review locks and submission gates."""
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

from adaptive_watch.assessment_entry import AssessmentEntry
from adaptive_watch.negative_review import Conflict, ReviewStore, digest
from adaptive_watch.workspace import Workspace
from adaptive_watch.workspace_api import handler

REPO = Path(__file__).resolve().parents[1]


class Decisions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = Workspace(REPO,root,root/'railway',root/'responses')
        # Decision contract fixture only; source validation is exercised separately.
        self.workspace.record = lambda case: dict(id=case,sourceRevision=digest(case),frames=[],camera=case)

    def tearDown(self):
        self.workspace.close()
        self.temp.cleanup()

    def act(self,case,action,**extra):
        return self.workspace.act(case,dict(action=action,revision=self.workspace.view(case)['revision'],**extra))

    def test_decisions_are_scoped_persisted_and_guarded(self):
        self.act('scooter','review')
        with self.assertRaisesRegex(ValueError,'acknowledge'):
            self.act('scooter','dismiss')
        self.act('scooter','dismiss',footageReviewed=True,note='Only scooter reviewed')
        self.act('gate','review')
        self.act('gate','save_review_request',footageReviewed=True,note='Gate mechanism uncertain')
        self.assertEqual(self.workspace.view('scooter')['state']['status'],'dismissed')
        self.assertEqual(self.workspace.view('gate')['state']['status'],'review_request_saved')
        self.assertEqual(self.workspace.view('bin')['state']['status'],'review_required')
        reopened = Workspace(REPO,self.workspace.root,self.workspace.railway,self.workspace.evaluations)
        reopened.record = self.workspace.record
        try:
            self.assertEqual(reopened.view('scooter')['state']['humanAnnotation']['note'],'Only scooter reviewed')
            self.assertEqual(reopened.db.execute('SELECT COUNT(*) FROM review_audit').fetchone()[0],4)
        finally:
            reopened.close()

    def test_cross_case_revisions_and_stale_decisions_rejected(self):
        initial = self.workspace.view('scooter')['revision']
        self.act('scooter','review')
        with self.assertRaises(Conflict):
            self.workspace.act('scooter',dict(action='dismiss',revision=initial,footageReviewed=True))
        with self.assertRaises(Conflict):
            self.workspace.act('bin',dict(action='review',revision=self.workspace.view('scooter')['revision']))
        self.assertEqual(self.workspace.view('bin')['state']['status'],'review_required')

    def test_changed_evidence_invalidates_decision(self):
        revision = self.workspace.view('gate')['revision']
        self.workspace.record = lambda case: dict(id=case,sourceRevision='changed',frames=[])
        with self.assertRaises(Conflict):
            self.workspace.act('gate',dict(action='review',revision=revision))
        self.assertEqual(self.workspace.db.execute('SELECT COUNT(*) FROM review_audit').fetchone()[0],0)


class AssessmentGates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.entry = AssessmentEntry(REPO,Path(self.temp.name))
        self.entry.configurations = lambda: dict(cameras=[dict(id='known',name='camera')],ready=False,blockers=[dict(code='authenticated_runtime_missing')])
        end = (datetime.now(timezone.utc)-timedelta(minutes=2)).replace(microsecond=0)
        self.body = dict(cameraId='known',start=(end-timedelta(seconds=15)).isoformat(),end=end.isoformat())

    def tearDown(self):
        self.temp.cleanup()

    def test_runtime_not_prepared_never_submits(self):
        result = self.entry.start(self.body)
        self.assertEqual(result['state'],'blocked')
        self.assertFalse(result['inferenceSubmitted'])
        self.assertFalse(result['recordingAcquired'])
        self.assertFalse((self.entry.root/'ledger.sqlite3').exists())
        self.assertTrue((self.entry.root/'assessment-readiness.sqlite3').exists())

    def test_unknown_camera_invalid_age_precision_and_window_rejected(self):
        for updates in (dict(cameraId='unknown'),dict(start='2026-10-22T11:04:48Z',end='2026-10-22T11:05:01Z'),
                        dict(start=self.body['end']),dict(start='2026-10-27T11:00:00'),dict(start='2026-10-27T11:00:00.123Z')):
            with self.subTest(updates=updates),self.assertRaises(ValueError):
                self.entry.start(self.body|updates)


class MissingSourceHTTP(unittest.TestCase):
    def test_missing_unknown_csrf_and_native_actions_fail_clearly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            server = ThreadingHTTPServer(('127.0.0.1',0),handler(root,root/'state',root/'railway',root/'evaluations',root/'frontend'))
            thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            try:
                data = json.load(opener.open(base+'/api/workspace'))
                self.assertEqual(data['records'],[])
                self.assertEqual(len(data['unavailable']),4)
                for path,status in (('/api/cases/unknown',404),('/api/cases/scooter',422),('/api/cases/gate/frames/0',422)):
                    with self.subTest(path=path),self.assertRaises(HTTPError) as caught:
                        opener.open(base+path)
                    self.assertEqual(caught.exception.code,status)
                    self.assertIn('error',json.load(caught.exception))
                for path in ('/api/assessments','/api/cases/bin/action','/api/native/send'):
                    with self.assertRaises(HTTPError) as caught:
                        opener.open(Request(base+path,data=b'{}',headers={'Content-Type':'application/json'}))
                    self.assertEqual(caught.exception.code,403)
            finally:
                server.shutdown();server.server_close();thread.join()


@unittest.skipUnless((REPO/'runs/hybrid/sidewalk-v2/scooter-joined.json').exists(), 'private saved sources unavailable')
class SavedSources(unittest.TestCase):
    def test_original_four_sources_and_changed_cv_fail_closed(self):
        railway = REPO/'runs/negative-result-review'
        store = ReviewStore(railway)
        try:
            record,_ = store.verified()
        finally:
            store.close()
        # Resolve the existing private evaluation root from the verified railway source.
        evaluations = next(Path(s['path']).parent for s in record['sources'] if Path(s['path']).parent.name == 'hafnia-16')
        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(REPO,Path(folder),railway,evaluations)
            try:
                index = workspace.index()
                self.assertEqual(index['unavailable'],[])
                self.assertEqual({r['id'] for r in index['records']},{'railway','gate','scooter','bin'})
                scooter,bin_case,gate = [workspace.view(key) for key in ('scooter','bin','gate')]
                self.assertEqual(scooter['runs'][0]['sampled_span_s'],5)
                self.assertEqual(bin_case['runs'][0]['sampled_span_s'],3)
                self.assertEqual(gate['runs'],[])
                self.assertTrue(all(f['box'] is None for f in gate['frames']))
                self.assertNotEqual(scooter['cameraGuid'],bin_case['cameraGuid'])
                # Removing the original evaluation directory blocks evidence on every
                # read, including image requests and review mutations.
                workspace.evaluations = Path(folder)/'missing-originals'
                with self.assertRaises(ValueError):workspace.view('scooter')
                with self.assertRaises(ValueError):workspace.view('gate',private=True)
                with self.assertRaises(ValueError):workspace.act('bin',dict(action='review',revision=bin_case['revision']))
            finally:
                workspace.close()
