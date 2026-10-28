"""Browser-started assessment: duplicate protection, resume without resubmission, truthful failure, loop check."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from adaptive_watch import assessment_job as aj
from adaptive_watch.assessment_job import Jobs, StageError, choose_interval, flag_loop, iso
from adaptive_watch.casebook import Casebook
from scene_contracts.gateway import GatewayError

REPO = Path(__file__).resolve().parents[1]
GUID = '1dfb0898-730f-44c1-bca8-7f541e8ef116'
CATALOG = tempfile.mkdtemp()
Path(CATALOG, 'cameras.local.json').write_text(json.dumps([dict(Name=aj.CAMERA, Id=GUID.upper())]))
ANSWER = json.dumps(dict(outcome='not_observed', evidence='People stand on the platform.', timing='unknown',
                         limitations='Short clip.'))


def sha(b):
    return hashlib.sha256(b).hexdigest()


class FakeRunner:
    def __init__(self, **fail):
        self.fail, self.calls = fail, []

    def sequences(self, camera):
        self.calls.append('sequences')
        now = datetime.now(timezone.utc)
        return [dict(start_utc=iso(now-timedelta(hours=1)), end_utc=iso(now-timedelta(seconds=5)))]

    def calibrate(self, sequences, now, out):
        self.calls.append('calibrate')
        if 'calibrate' in self.fail:
            raise self.fail['calibrate']
        return dict(seam_utc=iso(now-timedelta(seconds=400))[:-1]+'.013Z', period=15.0, seams=2, score=0.0, contrast=300.0)

    def check_window(self, manifest, offset, cycle=None):
        self.calls.append('check_window')
        return self.fail.get('window', dict(ok=True, firstPosition=offset, lastPosition=offset+12.0, maxError=0.1))

    def acquire(self, camera, start, end, out):
        self.calls.append('acquire')
        if 'acquire' in self.fail:
            raise self.fail['acquire']
        d = Path(out)/'cam_x'
        d.mkdir(parents=True)
        t0 = aj.parse(start)
        frames = []
        for i in range(31):
            data = f'frame{i}'.encode()
            (d/f'frame_{i:04d}.jpg').write_bytes(data)
            frames.append(dict(file=f'frame_{i:04d}.jpg', timestamp_utc=iso(t0+timedelta(seconds=i*.5)) , sha256=sha(data)))
        (d/'clip.mkv').write_bytes(b'mkv')
        m = dict(source='Get-Snapshot', camera_name=aj.CAMERA, camera_id=GUID, requested_start_utc=start, requested_end_utc=end,
                 frames=frames, mkv_export=dict(file='clip.mkv', sha256=sha(b'mkv')))
        (d/'manifest.json').write_text(json.dumps(m))
        return d/'manifest.json'

    def encode(self, manifest, out):
        self.calls.append('encode')
        if 'encode' in self.fail:
            raise self.fail['encode']
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out/'original.mp4').write_bytes(b'mp4')
        m = json.loads(Path(manifest).read_text())
        info = dict(file='original.mp4', sha256=sha(b'mp4'), sourceMkvSha256=m['mkv_export']['sha256'], fps=10, frames=150,
                    duration=15.0, samples=[dict(index=i, timestamp=f['timestamp_utc'], mediaTime=max(0, i*.5-.1), matchError=1.0)
                                            for i, f in enumerate(m['frames'])])
        (out/'media.json').write_text(json.dumps(info))
        return info, self.fail.get('diffs', [1.0+(i % 3)*.1 for i in range(149)])

    def run_cv(self, manifest, zone, out):
        self.calls.append('cv')
        if 'cv' in self.fail:
            raise self.fail['cv']
        m = json.loads(Path(manifest).read_text())
        obs = []
        for i, f in enumerate(m['frames']):
            inside = i >= 10 and not self.fail.get('never_inside')
            box = [0.7, 0.5, 0.9, 0.9] if inside else [0.0, 0.2, 0.2, 0.5]
            obs.append(dict(timestamp_utc=f['timestamp_utc'], objects=[dict(box=box, score=.9, track_id=1, t=i*.5, in_zone=inside),
                                                                      dict(box=[0.3, 0.1, 0.4, 0.2], score=.8, track_id=2, t=i*.5, in_zone=False)]))
        Path(out).write_text(json.dumps(dict(device='Fake GPU', model='fake', frames=len(obs), processing_s=1.5, observations=obs,
            tracks=[dict(track_id=1), dict(track_id=2)], manifest_sha256=sha(Path(manifest).read_bytes()),
            runner_sha256=aj.sha(REPO/aj.RUNNER_REL), tracker_sha256=aj.sha(REPO/aj.TRACKER_REL))))
        return out

    def hafnia(self, job_dir, entry, gateway_factory, on_state):
        self.calls.append('hafnia')
        if 'hafnia' in self.fail:
            raise self.fail['hafnia']
        return aj.run_hafnia(job_dir, entry, gateway_factory, lambda: self.fail.get('quota', dict(DailySummaryQuota=500, DailySummaryCount=1)), on_state, timeout=5)


class FakeGateway:
    def __init__(self, poll_error=None):
        self.posts, self.poll_error, self.request_payload = 0, poll_error, None

    def request(self, method, path, payload=None, login=False):
        if method == 'POST':
            self.posts += 1
            self.request_payload = payload
            return dict(Id='sum-1')
        if self.poll_error:
            raise self.poll_error
        return dict(Id='sum-1', Progress='Completed', Response=ANSWER, Request=self.request_payload)


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.jobs = []

    def tearDown(self):
        self.temp.cleanup()

    def make(self, runner=None, gateway=None, root=None, **kw):
        runner = runner or FakeRunner()
        gw = gateway or FakeGateway()
        jobs = Jobs(CATALOG, root or self.root, gateway_factory=lambda: gw, runner=runner, **kw)
        return jobs, runner, gw

    def settle(self, jobs, job_id):
        jobs.wait(job_id)
        return jobs.get(job_id)

    def to_continuity(self, jobs):
        job = jobs.start(dict(cameraId=GUID))
        job = self.settle(jobs, job['id'])
        return job

    def complete(self, jobs):
        job = self.to_continuity(jobs)
        self.assertEqual(job['state'], 'awaiting_continuity', job)
        jobs.confirm_continuity(dict(id=job['id'], reviewed=True))
        return self.settle(jobs, job['id'])


class Selection(unittest.TestCase):
    def test_interval_is_recent_whole_second_and_covered(self):
        now = datetime(2026, 10, 28, 12, 0, 7, 400000, tzinfo=timezone.utc)
        seq = [dict(start_utc='2026-10-28T10:00:00Z', end_utc='2026-10-28T12:00:07Z')]
        self.assertEqual(choose_interval(seq, now), ('2026-10-28T11:58:22Z', '2026-10-28T11:58:37Z'))

    def test_uses_sequence_end_when_recording_stopped(self):
        now = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
        seq = [dict(start_utc='2026-10-28T10:00:00Z', end_utc='2026-10-28T11:30:00Z')]
        self.assertEqual(choose_interval(seq, now)[1], '2026-10-28T11:30:00Z')

    def test_rejects_uncovered_ranges(self):
        now = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
        for seq in ([], [dict(start_utc='2026-10-28T11:59:50Z', end_utc='2026-10-28T11:59:59Z')],
                    [dict(start_utc='2026-10-28T11:59:00Z', end_utc='2026-10-28T11:59:10Z')]):
            with self.assertRaisesRegex(ValueError, 'retained recording'):
                choose_interval(seq, now)

    def test_loop_flag(self):
        calm = [1.0+(i % 3)*.1 for i in range(100)]
        self.assertFalse(flag_loop(calm)['flagged'])
        spike = calm[:40]+[30.0]+calm[41:]
        result = flag_loop(spike)
        self.assertTrue(result['flagged'])
        self.assertEqual(result['atSeconds'], 4.1)
        self.assertFalse(flag_loop([50.0]*5)['flagged'])  # too few frames to judge


class Lifecycle(Base):
    def test_full_run_completes_with_case(self):
        jobs, runner, gw = self.make()
        job = self.complete(jobs)
        self.assertEqual(job['state'], 'completed', job)
        self.assertEqual([s['status'] for s in job['stages']], ['done']*5)
        self.assertEqual(gw.posts, 1)
        case = jobs.live_case(job['id'])
        self.assertEqual(job['caseId'], case['id'])
        self.assertEqual(case['vision']['trackId'], 1)
        self.assertEqual(case['vision']['trigger']['index'], 10)
        self.assertEqual(case['hafnia']['verdict'], 'negative')
        self.assertTrue(case['handoff']['message'].startswith('Review exception'))

    def test_no_trigger_when_track_never_reaches_region(self):
        jobs, _, _ = self.make(FakeRunner(never_inside=True))
        case = jobs.live_case(self.complete(jobs)['id'])
        self.assertIsNone(case['vision']['trigger'])
        self.assertIsNone(case['vision']['trackId'])
        self.assertTrue(all(f['box'] is None and not f['near'] for f in case['frames']))
        self.assertIsNone(case['handoff'])

    def test_duplicate_click_returns_same_job_and_one_request(self):
        ticks = iter(range(10**6))
        jobs, runner, gw = self.make(clock=lambda: datetime.now(timezone.utc)+timedelta(seconds=next(ticks)*2))
        a = jobs.start(dict(cameraId=GUID))
        b = jobs.start(dict(cameraId=GUID))
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(runner.calls.count('sequences'), 1)
        job = self.settle(jobs, a['id'])
        self.assertEqual(jobs.start(dict(cameraId=GUID))['id'], a['id'])  # still waiting for continuity
        jobs.confirm_continuity(dict(id=a['id'], reviewed=True))
        self.settle(jobs, a['id'])
        self.assertEqual(gw.posts, 1)
        self.assertEqual(len(runner.calls) and runner.calls.count('acquire'), 1)

    def test_same_interval_row_is_unique(self):
        jobs, _, _ = self.make()
        with jobs._db() as db:
            db.execute("INSERT INTO jobs(id,camera,start,end,state,created,updated) VALUES ('a','c','s','e','failed','x','x')")
            with self.assertRaises(Exception):
                db.execute("INSERT INTO jobs(id,camera,start,end,state,created,updated) VALUES ('b','c','s','e','failed','x','x')")

    def test_continuity_confirmation_is_state_and_job_scoped(self):
        jobs, _, _ = self.make()
        job = self.to_continuity(jobs)
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            jobs.confirm_continuity(dict(id=job['id'], reviewed=False))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            jobs.confirm_continuity(dict(id='0'*32, reviewed=True))
        self.assertFalse((jobs.live/job['id']/'continuity.json').exists())
        jobs.confirm_continuity(dict(id=job['id'], reviewed=True))
        self.settle(jobs, job['id'])
        saved = json.loads((jobs.live/job['id']/'continuity.json').read_text())
        manifest = next((jobs.live/job['id']/'acquisition').glob('*/manifest.json'))
        self.assertEqual(saved['manifest_sha256'], sha(manifest.read_bytes()))
        with self.assertRaisesRegex(ValueError, 'not waiting'):
            jobs.confirm_continuity(dict(id=job['id'], reviewed=True))
        self.assertEqual(len(jobs.contact_frames(job['id'])), 31)

    def test_loop_boundary_fails_job_before_cv_or_hafnia(self):
        diffs = [1.0]*60+[40.0]+[1.0]*60
        jobs, runner, gw = self.make(FakeRunner(diffs=diffs))
        job = self.to_continuity(jobs)
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(job['error'], dict(reason='The recording appears to restart partway through', next='Choose a different interval.'))
        self.assertEqual(job['stages'][1]['status'], 'failed')
        self.assertNotIn('cv', runner.calls)
        self.assertEqual(gw.posts, 0)


class Failures(Base):
    def failed_stage(self, job):
        self.assertEqual(job['state'], 'failed', job)
        self.assertIsNotNone(job['error'])
        self.assertTrue(job['error']['reason'] and job['error']['next'])
        self.assertIsNone(job['caseId'])
        return [s['key'] for s in job['stages'] if s['status'] == 'failed']

    def test_acquisition_failure(self):
        jobs, _, gw = self.make(FakeRunner(acquire=StageError('XProtect would not provide the recording', 'Check it.')))
        job = self.to_continuity(jobs)
        self.assertEqual(self.failed_stage(job), ['acquisition'])
        self.assertIn('XProtect', job['error']['reason'])

    def test_encoding_failure_blocks_everything_after(self):
        jobs, runner, gw = self.make(FakeRunner(encode=ValueError('Snapshot 3 does not align with the original stream')))
        job = self.to_continuity(jobs)
        self.assertEqual(self.failed_stage(job), ['acquisition'])
        self.assertIn('align', job['error']['reason'])
        self.assertEqual(gw.posts, 0)

    def test_vision_failure_ssh_unreachable(self):
        err = StageError('The Linux GPU host is unreachable over SSH', 'Check p022-linux.')
        jobs, runner, gw = self.make(FakeRunner(cv=err))
        job = self.complete(jobs)
        self.assertEqual(self.failed_stage(job), ['vision'])
        self.assertIn('SSH', job['error']['reason'])
        self.assertEqual(gw.posts, 0)

    def test_quota_exhausted_reports_and_sends_nothing(self):
        jobs, _, gw = self.make(FakeRunner(quota=dict(DailySummaryQuota=500, DailySummaryCount=500)))
        job = self.complete(jobs)
        self.assertEqual(self.failed_stage(job), ['hafnia'])
        self.assertIn('allowance', job['error']['reason'])
        self.assertEqual(gw.posts, 0)

    def test_gateway_auth_rejected_on_submit_releases_claim(self):
        class Rejecting(FakeGateway):
            def request(self, method, path, payload=None, login=False):
                raise GatewayError('POST /api/Summaries failed (HTTP 401)')
        jobs, _, gw = self.make(gateway=Rejecting())
        job = self.complete(jobs)
        self.assertEqual(self.failed_stage(job), ['hafnia'])
        self.assertIn('rejected', job['error']['reason'])
        self.assertIn('Nothing was sent', job['error']['next'])

    def test_ambiguous_submit_is_never_retried(self):
        class Dropping(FakeGateway):
            def request(self, method, path, payload=None, login=False):
                self.posts += 1
                raise GatewayError('Cannot reach local Hafnia gateway')
        gw = Dropping()
        jobs, _, _ = self.make(gateway=gw)
        job = self.complete(jobs)
        self.assertEqual(self.failed_stage(job), ['hafnia'])
        self.assertIn('may or may not', job['error']['reason'])
        self.assertEqual(gw.posts, 1)
        again, _, _ = self.make(gateway=gw, root=self.root)  # restart: failure is final, not resumable
        self.assertEqual(again.get(job['id'])['state'], 'failed')
        self.assertEqual(gw.posts, 1)

    def test_hafnia_inference_failure(self):
        class Failing(FakeGateway):
            def request(self, method, path, payload=None, login=False):
                if method == 'POST':
                    return dict(Id='s')
                return dict(Id='s', Progress='Failed', LastError='model busy')
        jobs, _, _ = self.make(gateway=Failing())
        job = self.complete(jobs)
        self.assertEqual(self.failed_stage(job), ['hafnia'])
        self.assertIn('model busy', job['error']['reason'])

    def test_matching_failure_is_not_completed(self):
        jobs, _, _ = self.make()
        job = self.to_continuity(jobs)
        with mock.patch.object(aj, 'live_case', side_effect=ValueError('boom')):
            jobs.confirm_continuity(dict(id=job['id'], reviewed=True))
            job = self.settle(jobs, job['id'])
        self.assertEqual(self.failed_stage(job), ['matching'])
        self.assertNotIn(job['id'][:8], ' '.join(aj.completed_jobs(jobs.live)))


class Gatewayless(Base):
    def test_options_and_start_without_gateway_session(self):
        runner = FakeRunner()
        jobs = Jobs(CATALOG, self.root, runner=runner)
        o = jobs.options()
        self.assertFalse(o['available'])
        self.assertEqual(o['reason'], 'This server was started without a Hafnia gateway session.')
        self.assertIn('scripts\\launch.ps1', o['next'])
        self.assertEqual(o['cameras'][0]['title'], 'Station platform')
        with self.assertRaisesRegex(ValueError, 'gateway session'):
            jobs.start(dict(cameraId=GUID))
        self.assertEqual(runner.calls, [])

    def test_available_with_session_and_wrong_camera_rejected(self):
        jobs, _, _ = self.make()
        self.assertTrue(jobs.options()['available'])
        with self.assertRaisesRegex(ValueError, 'station platform'):
            jobs.start(dict(cameraId='7371DDCE-8938-42DA-8B83-B5E445166338'))

    def test_job_waiting_at_hafnia_never_calls_hafnia_without_session(self):
        class Stop(FakeRunner):
            def hafnia(self, *a):
                raise AssertionError('Hafnia stage must not run')
        jobs, _, _ = self.make(FakeRunner(hafnia=RuntimeError('stop')))
        job = self.complete(jobs)  # fails inside the fake stage after cv, state hafnia_*
        with jobs._db() as db:
            db.execute("UPDATE jobs SET state='hafnia_submitting',failed_stage=NULL,error=NULL WHERE id=?", (job['id'],))
        stop = Stop()
        jobs2 = Jobs(CATALOG, self.root, runner=stop)
        jobs2.wait(job['id'])
        got = jobs2.get(job['id'])
        self.assertEqual(got['state'], 'hafnia_submitting')
        self.assertEqual(got['stages'][3]['status'], 'needs_you')
        self.assertEqual(got['stages'][2]['status'], 'done')


class Restart(Base):
    def test_resume_polls_existing_request_without_resubmitting(self):
        broken = FakeGateway(poll_error=GatewayError('GET /api/Summaries/sum-1 failed (HTTP 500)'))
        jobs, _, _ = self.make(gateway=broken)
        job = self.complete(jobs)
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(broken.posts, 1)
        good = FakeGateway()
        good.request_payload = broken.request_payload
        jobs2, runner2, _ = self.make(gateway=good, root=self.root)
        jobs2.wait(job['id'])
        done = jobs2.get(job['id'])
        self.assertEqual(done['state'], 'completed', done)
        self.assertEqual(good.posts, 0)
        self.assertNotIn('acquire', runner2.calls)

    def test_claim_without_answer_is_reported_not_sent(self):
        jobs, _, gw = self.make()
        job = self.to_continuity(jobs)
        d = jobs.live/job['id']
        ev = aj.Evaluation(d/'hafnia')
        ev.db.execute("INSERT INTO submissions VALUES ('abc','{}',NULL,'submission_ambiguous')")
        ev.db.commit()
        ev.db.close()
        jobs.confirm_continuity(dict(id=job['id'], reviewed=True))
        done = self.settle(jobs, job['id'])
        self.assertEqual(done['state'], 'failed')
        self.assertIn('unknown', done['error']['reason'])
        self.assertEqual(gw.posts, 0)

    def test_restart_midway_does_not_redo_finished_stages(self):
        jobs, runner, gw = self.make()
        job = self.to_continuity(jobs)
        jobs2, runner2, _ = self.make(root=self.root)  # awaiting continuity is not auto-advanced
        self.assertEqual(jobs2.get(job['id'])['state'], 'awaiting_continuity')
        self.assertEqual(runner2.calls, [])


class Case(Base):
    KEYS = {'id', 'flagship', 'title', 'camera', 'interval', 'purpose', 'revision', 'actionRevision', 'kind', 'frames', 'video',
            'hafnia', 'vision', 'handoff', 'agent', 'state', 'native', 'diagnostic', 'provenance', 'limitations'}

    def test_schema_matches_railway_view(self):
        jobs, _, _ = self.make()
        case = jobs.live_case(self.complete(jobs)['id'])
        self.assertEqual(set(case), self.KEYS)
        self.assertEqual(set(case['frames'][0]), {'index', 'timestamp', 'mediaTime', 'box', 'distance', 'near', 'file'})
        self.assertEqual(set(case['video']), {'url', 'duration', 'fps', 'origin', 'sha256'})
        self.assertEqual(set(case['hafnia']), {'answer', 'verdict', 'quote', 'summaryId', 'request'})
        self.assertLessEqual({'label', 'model', 'trackId', 'region', 'trigger', 'regionStatus', 'samplesPerSecond', 'meaning'}, set(case['vision']))
        self.assertEqual(set(case['handoff']), {'event', 'camera', 'window', 'message', 'alarm'})
        self.assertRegex(case['handoff']['message'], r'from \d\d:\d\d\d?:?\d?')
        self.assertEqual(case['native']['state'], 'not_configured')
        self.assertNotIn('sentAt', case['native'])

    def test_tampered_evidence_blocks_case(self):
        jobs, _, _ = self.make()
        job = self.complete(jobs)
        (jobs.live/job['id']/'cv.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            jobs.live_case(job['id'])

    def test_casebook_lists_serves_and_scopes_actions(self):
        jobs, _, _ = self.make()
        job = self.complete(jobs)
        book = Casebook(REPO, self.root, self.root/'railway', self.root/'responses', self.root/'release')
        try:
            ids = [c['id'] for c in book.index()['cases']]
            self.assertEqual(ids, [job['caseId']])
            view = book.view(job['caseId'])
            files = book.live_files(job['caseId'])
            self.assertEqual(len(files['frames']), len(view['frames']))
            with self.assertRaises(Exception):
                book.act_live(job['caseId'], dict(action='review', revision='stale'))
            after = book.act_live(job['caseId'], dict(action='review', revision=view['actionRevision']))
            self.assertEqual(after['state']['status'], 'reviewing')
            done = book.act_live(job['caseId'], dict(action='request_xprotect_review', revision=after['actionRevision'],
                                                     footageReviewed=True, note='seen'))
            self.assertEqual(done['state']['status'], 'xprotect_review_requested')
            rows = book.ws.db.execute('SELECT case_id FROM reviews').fetchall()
            self.assertEqual(rows, [(job['caseId'],)])
            with self.assertRaises(KeyError):
                book.view('live-00000000')
            self.assertEqual(book.view('live-'+job['id'][:8])['native']['state'], 'not_configured')
        finally:
            book.close()

class Phase(Base):
    SEAM = '2026-10-28T11:00:00.013Z'

    def check(self, now, seqs):
        start, end = choose_interval(seqs, now, dict(seam_utc=self.SEAM, period=15.0))
        seam = aj.parse(self.SEAM).timestamp()
        s, e = aj.parse(start).timestamp(), aj.parse(end).timestamp()
        into = (s-seam) % 15
        self.assertGreaterEqual(into, .6)
        self.assertLessEqual(into+(e-s), 15-aj.TAIL_S+1e-6)  # stops before the next walk-in, not at the restart
        self.assertTrue(10 <= e-s <= 13)
        self.assertLessEqual(e, now.timestamp()-90)
        return start, end

    def test_window_never_contains_a_seam(self):
        base = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
        seqs = [dict(start_utc='2026-10-28T08:00:00Z', end_utc='2026-10-28T13:00:00Z')]
        for k in range(60):
            self.check(base+timedelta(seconds=k*1.37), seqs)

    def test_window_stops_before_the_next_walk_in(self):
        # 28 Oct 2026: the old window ended 1.5 s before the restart and its last frame already showed the next
        # walk-in (it begins ~13.3 s into the 15 s loop). The end now keeps TAIL_S clear of the restart instant.
        now = datetime(2026, 10, 28, 15, 36, 40, tzinfo=timezone.utc)
        seqs = [dict(start_utc='2026-10-28T14:00:00Z', end_utc='2026-10-28T16:00:00Z')]
        start, end = choose_interval(seqs, now, dict(seam_utc='2026-10-28T15:33:54.013Z', period=15.0))
        seam = aj.parse('2026-10-28T15:33:54.013Z').timestamp()
        self.assertLessEqual((aj.parse(end).timestamp()-seam) % 15, 13.0 + 1e-6)

    def test_continuity_note_never_claims_a_person(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'a').mkdir()
            (Path(d)/'a'/'continuity.json').write_text(json.dumps(dict(manifest_sha256='x', reviewed_at='t')))
            note = aj.continuity_note(d, 'a')
            self.assertNotIn('A person confirmed', note)
            self.assertIn('did not record who', note)
            (Path(d)/'a'/'continuity.json').write_text(json.dumps(dict(reviewer='Claude demo reviewer (AI)')))
            self.assertIn('Claude demo reviewer (AI)', aj.continuity_note(d, 'a'))

    def test_phased_window_must_be_covered(self):
        now = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
        start, end = self.check(now, [dict(start_utc='2026-10-28T08:00:00Z', end_utc='2026-10-28T11:30:00Z')])
        self.assertLessEqual(end, '2026-10-28T11:30:00Z')
        with self.assertRaisesRegex(ValueError, 'retained recording'):
            choose_interval([dict(start_utc='2026-10-28T11:59:00Z', end_utc='2026-10-28T11:59:20Z')], now, dict(seam_utc=self.SEAM, period=15.0))

    def test_phase_is_persisted_and_reused(self):
        jobs, runner, _ = self.make()
        self.complete(jobs)
        self.assertEqual(runner.calls.count('calibrate'), 1)
        saved = json.loads((jobs.live/'phase.json').read_text())
        self.assertIn('calibrated_at', saved)
        jobs.start(dict(cameraId=GUID))
        self.assertEqual(runner.calls.count('calibrate'), 1)
        job = json.loads((next(jobs.live.glob('*/job.json'))).read_text())
        self.assertIn('offset', job['loop'])

    def test_stale_phase_is_remeasured(self):
        jobs, runner, _ = self.make()
        (jobs.live/'phase.json').write_text(json.dumps(dict(seam_utc=self.SEAM, period=15.0, calibrated_at='2020-01-01T00:00:00+00:00')))
        self.to_continuity(jobs)
        self.assertEqual(runner.calls.count('calibrate'), 1)

    def test_failed_validation_fails_job_and_drops_phase(self):
        jobs, runner, gw = self.make(FakeRunner(window=dict(ok=False, reason='snapshots differ from the clip')))
        job = self.to_continuity(jobs)
        self.assertEqual(job['state'], 'failed')
        self.assertEqual([s['key'] for s in job['stages'] if s['status'] == 'failed'], ['continuity'])
        self.assertIn('loop timing', job['error']['reason'])
        self.assertFalse((jobs.live/'phase.json').exists())
        self.assertNotIn('cv', runner.calls)
        self.assertEqual(gw.posts, 0)

    def test_calibration_failure_is_reported_and_creates_no_job(self):
        jobs, _, _ = self.make(FakeRunner(calibrate=StageError('Could not time the camera loop', 'Try again.')))
        with self.assertRaisesRegex(ValueError, 'time the camera loop'):
            jobs.start(dict(cameraId=GUID))
        with jobs._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)

    def test_continuity_detail_is_honest(self):
        jobs, _, _ = self.make()
        job = self.to_continuity(jobs)
        text = job['stages'][1]['detail']
        self.assertIn('starts after the clip start and ends before it repeats', text)


class Fixes(Base):
    def test_poll_clears_stale_outcome(self):
        from adaptive_watch.evaluation import Evaluation
        ev = Evaluation(self.root/'ev')
        record = dict(summary=dict(Id='x'), poll_outcome='malformed_response', malformed_poll_response={'a': 1})
        try:
            record = ev.poll(FakeGateway(), 'd', record, timeout=5)
        finally:
            ev.db.close()
        self.assertNotIn('poll_outcome', record)
        self.assertNotIn('malformed_poll_response', record)
        self.assertEqual(record['parsed']['outcome'], 'not_observed')

    def test_resumed_poll_after_unreadable_status_completes(self):
        class Flaky(FakeGateway):
            n = 0

            def request(self, method, path, payload=None, login=False):
                if method == 'GET' and Flaky.n == 0:
                    Flaky.n += 1
                    return 'garbage'
                return super().request(method, path, payload, login)
        jobs, runner, gw = self.make(gateway=Flaky())
        job = self.complete(jobs)
        self.assertEqual(job['state'], 'failed')  # unreadable status is reported, not hidden
        again, _, _ = self.make(gateway=Flaky(), root=self.root)  # resumed: polled afresh, not resent
        again.wait(job['id'])
        self.assertEqual(again.get(job['id'])['state'], 'completed')

    def test_hms_format(self):
        self.assertEqual(aj.hms('2026-10-22T11:03:48.513Z'), '11:03:48.5')
        self.assertEqual(aj.hms('2026-10-22T11:03:48Z'), '11:03:48.0')
        self.assertEqual(aj.hms('2026-10-22T11:03:48.013Z'), '11:03:48.0')

    def test_stage_error_is_a_value_error(self):
        self.assertTrue(issubclass(StageError, ValueError))
        self.assertEqual(str(StageError('why', 'next')), 'why')

    def test_failed_job_allows_fresh_job_for_same_interval(self):
        now = datetime.now(timezone.utc)
        runner = FakeRunner(acquire=StageError('XProtect would not provide the recording', 'Try again.'))
        jobs, _, gw = self.make(runner, clock=lambda: now)
        first = self.settle(jobs, jobs.start(dict(cameraId=GUID))['id'])
        self.assertEqual(first['state'], 'failed')
        runner.fail.pop('acquire')
        second = jobs.start(dict(cameraId=GUID))
        self.assertNotEqual(second['id'], first['id'])
        self.assertEqual(second['interval'], first['interval'])
        self.assertEqual(self.settle(jobs, second['id'])['state'], 'awaiting_continuity')
        self.assertEqual(jobs.get(first['id'])['state'], 'failed')

    def test_interval_with_a_hafnia_claim_never_gets_a_second_job(self):
        class Dropping(FakeGateway):
            def request(self, method, path, payload=None, login=False):
                self.posts += 1
                raise GatewayError('Cannot reach local Hafnia gateway')
        now = datetime.now(timezone.utc)
        gw = Dropping()
        jobs, _, _ = self.make(gateway=gw, clock=lambda: now)
        first = self.complete(jobs)
        self.assertEqual(first['state'], 'failed')
        again = jobs.start(dict(cameraId=GUID))
        self.assertEqual(again['id'], first['id'])
        self.assertEqual(gw.posts, 1)

    def test_verification_is_cached_until_a_file_changes(self):
        jobs, _, _ = self.make()
        job = self.complete(jobs)
        aj._CACHE.clear()
        with mock.patch.object(aj, 'sha', wraps=aj.sha) as counted:
            aj.case_files(jobs.live, job['id'])
            first = counted.call_count
            for _ in range(5):
                aj.case_files(jobs.live, job['id'])
            self.assertEqual(counted.call_count, first)
            self.assertGreater(first, 0)
            jobs.contact_frames(job['id'])
            second = counted.call_count
            jobs.contact_frames(job['id'])
            jobs.contact_frames(job['id'])
            self.assertEqual(counted.call_count, second)
        (jobs.live/job['id']/'media/original.mp4').write_bytes(b'mp4 changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            aj.case_files(jobs.live, job['id'])
        jobs.contact_frames(job['id'])[0].write_bytes(b'altered!')
        with self.assertRaises(StageError):
            jobs.contact_frames(job['id'])


if __name__ == '__main__':
    unittest.main()
