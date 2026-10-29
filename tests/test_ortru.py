"""Ortru: policy, capability registry, Watch versions, scheduler, quotas, exception view, review decisions, native handoff."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from adaptive_watch import assessment_job as aj
from adaptive_watch.assessment_job import StageError, iso
from ortru import policy
from ortru.capabilities import check_detector, validate_region
from ortru.engine import Engine
from ortru.exceptions import Reviews, Stale, build_view
from ortru.loops import estimate, find_jumps
from ortru.native import Native
from ortru.watches import Conflict, Watches, build_prompt

REPO = Path(__file__).resolve().parents[1]
GUID = '1dfb0898-730f-44c1-bca8-7f541e8ef116'
GUID2 = '2de5fcf8-9c47-48da-9d1e-1ee32a595a94'
CATALOG = [dict(id=GUID.upper(), name='person_on_railway_tracks'), dict(id=GUID2.upper(), name='vandalism')]
DEST = {GUID: 'Adaptive Watch review: station platform'}
ANSWER = json.dumps(dict(outcome='not_observed', evidence='People stand on the platform.', timing='unknown', limitations='Short clip.'))
REGION = dict(polygon=[[0.25, 0.32], [1.0, 0.67], [1.0, 1.0], [0.62, 1.0]])


def sha(b):
    return hashlib.sha256(b).hexdigest()


def config(**over):
    base = dict(name='Platform edge', cameraId=GUID, hafnia=dict(instruction='A person climbs down from the platform edge onto the track area',
                condition='Person on the track area'), detector=dict(id='person_region_proximity', parameters=dict(margin=0)), region=REGION,
                schedule=dict(intervalMinutes=15, windowSeconds=15), quota=dict(perDay=20), policy=dict(raiseOn=['disagreement', 'corroborated', 'unresolved']))
    base.update(over)
    return base


class FakeRunner:
    def __init__(self, **fail):
        self.fail, self.calls = fail, []

    def phase(self, cfg, sequences, now, root):
        return None

    def sequences(self, camera):
        self.calls.append('sequences')
        if 'sequences' in self.fail:
            raise self.fail['sequences']
        now = datetime.now(timezone.utc)
        return self.fail.get('seq', [dict(start_utc=iso(now-timedelta(hours=1)), end_utc=iso(now-timedelta(seconds=5)))])

    def acquire(self, camera, start, end, out, interval='0.5', mkv=True):
        self.calls.append('acquire')
        d = Path(out)/'cam_x'
        d.mkdir(parents=True)
        t0 = aj.parse(start)
        frames = []
        for i in range(31):
            data = f'frame{i}'.encode()
            (d/f'frame_{i:04d}.jpg').write_bytes(data)
            frames.append(dict(file=f'frame_{i:04d}.jpg', timestamp_utc=iso(t0+timedelta(seconds=i*.5)), sha256=sha(data)))
        (d/'clip.mkv').write_bytes(b'mkv')
        gid = next(c['id'] for c in CATALOG if c['name'] == camera)
        m = dict(source='Get-Snapshot', camera_name=camera, camera_id=gid, requested_start_utc=start, requested_end_utc=end,
                 frames=frames, mkv_export=dict(file='clip.mkv', sha256=sha(b'mkv')))
        (d/'manifest.json').write_text(json.dumps(m))
        return d/'manifest.json'

    def encode(self, manifest, out):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out/'original.mp4').write_bytes(b'mp4')
        m = json.loads(Path(manifest).read_text())
        info = dict(file='original.mp4', sha256=sha(b'mp4'), sourceMkvSha256=m['mkv_export']['sha256'], fps=10, frames=150, duration=15.0,
                    samples=[dict(index=i, timestamp=f['timestamp_utc'], mediaTime=max(0, i*.5-.1), matchError=1.0) for i, f in enumerate(m['frames'])])
        (out/'media.json').write_text(json.dumps(info))
        return info, self.fail.get('diffs', [1.0+(i % 3)*.1 for i in range(149)])

    def run_cv(self, manifest, zone, out):
        self.calls.append('cv')
        if 'cv' in self.fail:
            raise self.fail['cv']
        m = json.loads(Path(manifest).read_text())
        polygon = json.loads(Path(zone).read_text())['polygon']
        obs = []
        for i, f in enumerate(m['frames']):
            inside = i >= 10 and not self.fail.get('never_inside')
            box = [0.7, 0.5, 0.9, 0.9] if inside else [0.0, 0.2, 0.2, 0.5]
            obs.append(dict(timestamp_utc=f['timestamp_utc'], objects=[dict(box=box, score=.9, track_id=1, t=i*.5, in_zone=inside)]))
        Path(out).write_text(json.dumps(dict(device='Fake GPU', model='fake', frames=len(obs), processing_s=1.5, observations=obs, polygon=polygon,
                                             tracks=[dict(track_id=1)], manifest_sha256=sha(Path(manifest).read_bytes()))))
        return out

    def hafnia(self, job_dir, entry, gateway_factory, on_state):
        self.calls.append('hafnia')
        if 'hafnia' in self.fail:
            raise self.fail['hafnia']
        self.entry = entry
        return aj.run_hafnia(job_dir, entry, gateway_factory, lambda: dict(DailySummaryQuota=500, DailySummaryCount=1), on_state, timeout=5)


class FakeGateway:
    def __init__(self, answer=ANSWER):
        self.posts, self.answer, self.payload = 0, answer, None

    def request(self, method, path, payload=None, login=False):
        if method == 'POST':
            self.posts += 1
            self.payload = payload
            return dict(Id='sum-%d' % self.posts)
        return dict(Id=path.rsplit('/', 1)[1], Progress='Completed', Response=self.answer, Request=self.payload)


class FakeConnection:
    sent = []

    def __init__(self, host, port, timeout=10):
        self.host, self.port = host, port

    def request(self, method, path, body=None, headers=None):
        FakeConnection.sent.append((self.host, self.port, body))

    def getresponse(self):
        class R:
            status = 200

            def read(self, n):
                return b''
        return R()

    def close(self):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.watches = Watches(self.root/'ortru.sqlite3', CATALOG, DEST)
        FakeConnection.sent = []
        self.engines = []

    def tearDown(self):
        for e in self.engines:
            for t in list(e.threads.values()):
                t.join(10)
        self.temp.cleanup()

    def engine(self, runner=None, gateway=None, **kw):
        gw = FakeGateway() if gateway is None else gateway
        eng = Engine(self.root, self.watches, runner or FakeRunner(), gateway_factory=(lambda: gw) if gw is not False else None, **kw)
        self.engines.append(eng)
        return eng

    def run_watch(self, eng, wid=None, **kw):
        w = wid or self.watches.create(config(**kw))['id']
        self.watches.set_status(w, 'active')
        job = eng.start(w)
        eng.wait(job['id'])
        return w, eng.get(job['id'])


class Policy(unittest.TestCase):
    def test_matrix(self):
        cases = {('not_observed', 'triggered'): ('disagreement', True), ('observed', 'triggered'): ('corroborated', True),
                 ('uncertain', 'triggered'): ('unresolved', True), ('malformed', 'triggered'): ('unresolved', True),
                 ('observed', 'none'): ('hafnia_only', False), ('not_observed', 'none'): ('clear', False),
                 ('uncertain', 'none'): ('inconclusive', False), ('malformed', 'none'): ('inconclusive', False)}
        for (h, v), (kind, raised) in cases.items():
            r = policy.decide(h, v)
            self.assertEqual((r['kind'], r['raised']), (kind, raised), (h, v))

    def test_malformed_is_never_negative(self):
        self.assertEqual(policy.hafnia_outcome(dict(parsed=dict(category='malformed_format'))), 'malformed')
        self.assertEqual(policy.hafnia_outcome(None), 'malformed')
        self.assertEqual(policy.hafnia_outcome(dict(parsed=dict(category='valid_model_decision', outcome='not_observed'))), 'not_observed')

    def test_watch_can_choose_to_raise_hafnia_only(self):
        self.assertTrue(policy.decide('observed', 'none', ('hafnia_only',))['raised'])

    def test_unknown_signal_refused(self):
        with self.assertRaises(ValueError):
            policy.decide('maybe', 'none')


class Capabilities(unittest.TestCase):
    def test_supported_detector_and_region(self):
        det, region = check_detector(dict(id='person_region_proximity'), REGION)
        self.assertEqual(det['parameters'], dict(margin=0))
        self.assertEqual(len(region['polygon']), 4)

    def test_unsupported_detector_explained(self):
        with self.assertRaisesRegex(ValueError, 'not available: Needs the object-localization'):
            check_detector(dict(id='object_stationarity'), REGION)
        with self.assertRaisesRegex(ValueError, 'Unknown detector'):
            check_detector(dict(id='anything goes'), REGION)

    def test_bad_parameters_and_regions(self):
        for det in (dict(id='person_region_proximity', parameters=dict(margin=5)), dict(id='person_region_proximity', parameters=dict(x=1))):
            with self.assertRaises(ValueError):
                check_detector(det, REGION)
        for region in (None, dict(polygon=[[0, 0], [1, 1]]), dict(polygon=[[0, 0], [2, 0], [1, 1]]), dict(polygon=[[0, 0], [0.01, 0], [0, 0.01]])):
            with self.assertRaises(ValueError):
                validate_region(region)


class WatchStore(Base):
    def test_create_edit_versions_and_lifecycle(self):
        w = self.watches.create(config())
        self.assertEqual((w['status'], w['version']), ('draft', 1))
        self.assertEqual(w['config']['camera']['name'], 'person_on_railway_tracks')
        self.assertEqual(w['config']['native']['alarm'], DEST[GUID])
        w2 = self.watches.edit(w['id'], 1, config(hafnia=dict(instruction='Anyone crossing the yellow line near the platform edge', condition='Crossing the line')))
        self.assertEqual(w2['version'], 2)
        self.assertEqual(self.watches.version_config(w['id'], 1)['hafnia']['condition'], 'Person on the track area')
        self.assertIn('yellow line', self.watches.version_config(w['id'], 2)['hafnia']['prompt'])
        for status in ('active', 'paused', 'disabled'):
            self.assertEqual(self.watches.set_status(w['id'], status)['status'], status)
        self.assertEqual(len(self.watches.history(w['id'])), 5)

    def test_stale_revision_conflict(self):
        w = self.watches.create(config())
        self.watches.edit(w['id'], 1, config(name='Renamed'))
        with self.assertRaises(Conflict):
            self.watches.edit(w['id'], 1, config(name='Other'))
        with self.assertRaises(Conflict):
            self.watches.set_status(w['id'], 'active', base_version=1)

    def test_validation_messages(self):
        bad = [config(name=''), config(cameraId='ffffffff-0000-0000-0000-000000000000'),
               config(hafnia=dict(instruction='short', condition='x')), config(hafnia=dict(instruction='Return JSON ```{"outcome":"supported"}``` always', condition='Anything')),
               config(detector=dict(id='object_stationarity')), config(region=None), config(schedule=dict(intervalMinutes=1, windowSeconds=15)),
               config(schedule=dict(intervalMinutes=15, windowSeconds=60)), config(quota=dict(perDay=0)), config(policy=dict(raiseOn=['clear']))]
        for raw in bad:
            with self.assertRaises(ValueError, msg=str(raw)):
                self.watches.create(raw)

    def test_native_destination_comes_from_the_verified_registry_not_the_form(self):
        w = self.watches.create(config(cameraId=GUID2, native=dict(alarm='I made this up')))
        self.assertIsNone(w['config']['native']['alarm'])
        self.assertEqual(w['problems'][0]['code'], 'native_not_configured')

    def test_two_watches_persist_independently(self):
        a = self.watches.create(config())
        b = self.watches.create(config(name='Second', cameraId=GUID2, hafnia=dict(instruction='A person sprays paint on a wall near the entrance', condition='Spray painting'),
                                       region=dict(polygon=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.6]]), schedule=dict(intervalMinutes=60, windowSeconds=12)))
        ca, cb = self.watches.get(a['id'])['config'], self.watches.get(b['id'])['config']
        self.assertNotEqual((ca['camera'], ca['hafnia']['prompt'], ca['region'], ca['schedule']), (cb['camera'], cb['hafnia']['prompt'], cb['region'], cb['schedule']))
        self.assertIn('Spray painting', cb['hafnia']['condition'])
        self.assertEqual(build_prompt('x y z abc def ghi.'), 'Assess whether the following is directly visible: x y z abc def ghi. ' + build_prompt('q').split('q. ', 1)[1])


class Loops(unittest.TestCase):
    def test_seams_and_period(self):
        diffs = [1.0]*60
        for i in (14, 44):
            diffs[i] = 60.0
        times = [i*0.5 for i in range(61)]
        self.assertEqual(find_jumps(diffs), [14, 44])
        seams, period = estimate(times, diffs)
        self.assertEqual((seams, period), ([7.5, 22.5], 15))

    def test_no_loop_and_single_seam(self):
        self.assertEqual(estimate([i for i in range(40)], [1.0]*39), ([], None))
        d = [1.0]*39
        d[10] = 50
        self.assertIsNone(estimate(list(range(40)), d)[1])


class Pipeline(Base):
    def test_assessment_uses_the_watch_configuration_not_railway_constants(self):
        eng, gw = self.engine(), FakeGateway()
        eng = self.engine(gateway=gw)
        w, job = self.run_watch(eng)
        self.assertEqual(job['state'], 'completed', job)
        self.assertEqual(gw.posts, 1)
        self.assertIn('climbs down from the platform edge', gw.payload['Prompt'])
        view = build_view(eng, job['id'])
        self.assertTrue(view['raised'])
        self.assertEqual(view['policy']['kind'], 'disagreement')
        self.assertEqual(view['watch']['version'], 1)
        self.assertEqual(view['review']['question'], 'Is "Person on the track area" visible in the footage?')
        self.assertEqual([o['label'] for o in view['review']['options']][:2], ['Person on the track area: yes', 'Person on the track area: no'])
        self.assertIn('Person on the track area', view['reason'])
        self.assertEqual(view['vision']['trigger']['index'], 10)

    def test_second_watch_other_camera_prompt_region_runs_through_the_same_code(self):
        gw = FakeGateway()
        eng = self.engine(gateway=gw)
        w, job = self.run_watch(eng, name='Wall', cameraId=GUID2, hafnia=dict(instruction='A person sprays paint on a wall near the entrance', condition='Spray painting'),
                                region=dict(polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]]))
        self.assertEqual(job['state'], 'completed', job)
        self.assertIn('sprays paint', gw.payload['Prompt'])
        self.assertNotIn('platform', gw.payload['Prompt'])
        view = build_view(eng, job['id'])
        self.assertEqual(view['camera']['name'], 'vandalism')
        self.assertIsNone(view['handoff']['alarm'])
        self.assertEqual(Native('x.sqlite3', '127.0.0.1:9', True, 'y.json').state(view)['state'], 'not_configured')
        outcomes = {o['id']: o for o in view['review']['outcomes']}
        self.assertFalse(outcomes['escalate']['enabled'])
        self.assertIn('No XProtect alarm', outcomes['escalate']['why'])

    def test_completed_assessment_keeps_exact_version_after_edit(self):
        eng = self.engine()
        w, job = self.run_watch(eng)
        self.watches.edit(w, 1, config(hafnia=dict(instruction='A person stands behind the yellow safety line', condition='Behind the line')))
        view = build_view(eng, job['id'])
        self.assertEqual(view['watch']['version'], 1)
        self.assertIn('climbs down', view['hafnia']['prompt'])
        self.assertEqual(view['provenance']['watchConfig']['hafnia']['condition'], 'Person on the track area')

    def test_no_gateway_parks_visibly_and_sends_nothing(self):
        eng = self.engine(gateway=False)
        w, job = self.run_watch(eng)
        self.assertEqual(job['state'], 'hafnia_submitting')
        stage = job['stages'][2]
        self.assertEqual(stage['status'], 'needs_you')
        self.assertIn('gateway', stage['detail'])
        self.assertNotIn('hafnia', eng.runner.calls)

    def test_interval_dedup_budget_and_running_guard(self):
        runner, gw = FakeRunner(), FakeGateway()
        eng = self.engine(runner, gw)
        w, first = self.run_watch(eng)
        again = eng.start(w)
        self.assertEqual(again, dict(id=first['id'], created=False))
        self.assertEqual(gw.posts, 1)
        # a different window is allowed and counted against the daily budget
        self.watches.edit(w, 1, config(quota=dict(perDay=1)))
        with self.assertRaisesRegex(ValueError, 'budget of 1'):
            eng.start(w)

    def test_global_limit(self):
        eng = self.engine(global_per_day=1)
        w, job = self.run_watch(eng)
        w2 = self.watches.create(config(name='Another', cameraId=GUID2))
        self.watches.set_status(w2['id'], 'active')
        with self.assertRaisesRegex(ValueError, 'All Watches together'):
            eng.start(w2['id'])

    def test_tick_respects_cadence_paused_and_disabled(self):
        eng = self.engine()
        w = self.watches.create(config())['id']
        self.assertEqual(eng.tick(), [])  # a draft is not scheduled
        self.watches.set_status(w, 'active')
        started = eng.tick()
        self.assertEqual(len(started), 1)
        eng.wait(started[0])
        self.assertEqual(eng.tick(), [])  # cadence not yet due
        self.assertIsNotNone(eng.schedule_view(self.watches.get(w))['nextDue'])
        self.watches.set_status(w, 'paused')
        self.assertIsNone(eng.schedule_view(self.watches.get(w))['nextDue'])
        later = Engine(self.root, self.watches, FakeRunner(), gateway_factory=lambda: FakeGateway(), clock=lambda: datetime.now(timezone.utc)+timedelta(hours=1), resume=False)
        self.assertEqual(later.tick(), [])

    def test_expired_or_missing_recording_fails_before_hafnia(self):
        eng = self.engine(FakeRunner(seq=[]))
        w = self.watches.create(config())['id']
        self.watches.set_status(w, 'active')
        with self.assertRaisesRegex(ValueError, 'no retained recording'):
            eng.start(w)
        self.assertIn('no retained recording', eng.schedule_view(self.watches.get(w))['lastCheck']['text'])

    def test_recording_expires_between_queue_and_acquire(self):
        runner = FakeRunner()
        eng = self.engine(runner)
        w = self.watches.create(config())['id']
        self.watches.set_status(w, 'active')
        job = eng.start(w)
        eng.wait(job['id'])
        runner.fail['seq'] = []
        with eng.db() as db:
            db.execute("UPDATE assessments SET state='queued',details='{}' WHERE id=?", (job['id'],))
        import shutil
        shutil.rmtree(eng.dir(job['id'])/'acquisition')
        eng._kick(job['id'])
        eng.wait(job['id'])
        j = eng.get(job['id'])
        self.assertEqual(j['state'], 'failed')
        self.assertIn('expired', j['error']['reason'])

    def test_failed_job_shows_exact_reason_and_retry_before_hafnia(self):
        runner = FakeRunner(cv=StageError('Local vision failed on the Linux GPU host: CUDA error', 'Check the GPU on p022-linux, then start again.'))
        eng = self.engine(runner)
        w, job = self.run_watch(eng)
        self.assertEqual((job['state'], job['stages'][1]['status']), ('failed', 'failed'))
        self.assertIn('CUDA error', job['error']['reason'])
        runner.fail.clear()
        eng.retry(job['id'])
        eng.wait(job['id'])
        self.assertEqual(eng.get(job['id'])['state'], 'completed')

    def test_uncertain_hafnia_transport_blocks_another_request(self):
        class Boom(FakeGateway):
            def request(self, method, path, payload=None, login=False):
                if method == 'POST':
                    self.posts += 1
                    raise OSError('reset')
                return super().request(method, path, payload, login)
        gw = Boom()
        eng = self.engine(gateway=gw)
        w, job = self.run_watch(eng)
        self.assertEqual(job['state'], 'failed')
        self.assertIn('may or may not have reached', job['error']['reason'])
        with self.assertRaisesRegex(ValueError, 'will not be sent again'):
            eng.retry(job['id'])
        again = eng.start(w)
        self.assertFalse(again['created'])
        self.assertEqual(gw.posts, 1)

    def test_resume_after_restart_does_not_resend(self):
        gw = FakeGateway()
        eng = self.engine(gateway=False)
        w, job = self.run_watch(eng)
        self.assertEqual(job['state'], 'hafnia_submitting')
        eng2 = Engine(self.root, self.watches, FakeRunner(), gateway_factory=lambda: gw)
        eng2.wait(job['id'])
        self.assertEqual(eng2.get(job['id'])['state'], 'completed')
        eng3 = Engine(self.root, self.watches, FakeRunner(), gateway_factory=lambda: gw)
        self.assertEqual(gw.posts, 1)

    def test_loop_restart_in_window_fails_before_vision(self):
        diffs = [1.0]*149
        diffs[60] = 80.0
        eng = self.engine(FakeRunner(diffs=diffs))
        w, job = self.run_watch(eng)
        self.assertEqual(job['state'], 'failed')
        self.assertIn('restart partway', job['error']['reason'])
        self.assertNotIn('cv', eng.runner.calls)

    def test_malformed_hafnia_answer_is_unresolved_not_negative(self):
        eng = self.engine(gateway=FakeGateway(answer='the answer is probably no'))
        w, job = self.run_watch(eng)
        view = build_view(eng, job['id'])
        self.assertEqual((view['hafnia']['outcome'], view['policy']['kind']), ('malformed', 'unresolved'))
        self.assertTrue(view['raised'])
        self.assertNotEqual(view['hafnia']['answer'], 'Not observed')

    def test_no_person_near_region_is_clear_and_not_raised(self):
        eng = self.engine(FakeRunner(never_inside=True))
        w, job = self.run_watch(eng)
        view = build_view(eng, job['id'])
        self.assertEqual((view['policy']['kind'], view['raised'], view['handoff']), ('clear', False, None))


class ReviewAndNative(Base):
    def exception(self):
        eng = self.engine()
        w, job = self.run_watch(eng)
        return eng, job['id']

    def test_decision_persists_with_revision_and_rejects_stale(self):
        eng, eid = self.exception()
        reviews = Reviews(eng)
        view = build_view(eng, eid, reviews.get(eid))
        body = dict(expectedRevision=0, verdict='visible', note='Person on the track bed', watchedFootage=True, outcome='escalate')
        d = reviews.decide(eid, body, view)
        self.assertEqual((d['revision'], d['status']), (1, 'review_requested'))
        self.assertEqual(Reviews(eng).get(eid)['note'], 'Person on the track bed')
        with self.assertRaises(Stale):
            reviews.decide(eid, body, view)
        self.assertEqual(Reviews(eng).get('other')['status'], 'undecided')

    def test_decision_rules(self):
        eng, eid = self.exception()
        reviews = Reviews(eng)
        view = build_view(eng, eid, reviews.get(eid))
        ok = dict(expectedRevision=0, verdict='visible', note='x', watchedFootage=True, outcome='escalate')
        for bad in (dict(ok, watchedFootage=False), dict(ok, verdict='The condition'), dict(ok, outcome='send'), dict(ok, note=''), dict(ok, note='x'*2000)):
            with self.assertRaises(ValueError):
                reviews.decide(eid, bad, view)
        self.assertEqual(reviews.get(eid)['revision'], 0)
        self.assertEqual(reviews.decide(eid, dict(ok, outcome='dismiss', verdict='unclear', note=''), view)['status'], 'dismissed')

    def native(self, enabled=True):
        return Native(self.root/'ledger.sqlite3', '127.0.0.1:9090', enabled, self.root/'status.json', connection=FakeConnection)

    def test_send_needs_approval_goes_through_ledger_and_cannot_repeat(self):
        eng, eid = self.exception()
        view = build_view(eng, eid)
        n = self.native()
        self.assertEqual(n.state(view)['state'], 'ready')
        preview = n.preview(view)
        self.assertIn('Ortru', preview['xml'])
        with self.assertRaises(ValueError):
            n.send(view, 'deadbeefdeadbeef')
        self.assertEqual(FakeConnection.sent, [])
        row = n.send(view, preview['sha256'][:16])
        self.assertEqual(row['state'], 'accepted')
        self.assertEqual(len(FakeConnection.sent), 1)
        state = n.state(view)
        self.assertEqual((state['state'], state['transport']['state'], state['smartClient']), ('sent', 'accepted', 'not_verified'))
        with self.assertRaises(ValueError):
            n.send(view, preview['sha256'][:16])
        self.assertEqual(len(FakeConnection.sent), 1)

    def test_sending_disabled_and_unconfigured(self):
        eng, eid = self.exception()
        view = build_view(eng, eid)
        with self.assertRaisesRegex(ValueError, 'switched off'):
            self.native(False).send(view, 'a'*12)
        self.assertEqual(FakeConnection.sent, [])

    def test_real_transport_is_never_used_by_default_in_tests(self):
        self.assertIs(self.native().connection, FakeConnection)


if __name__ == '__main__':
    unittest.main()
