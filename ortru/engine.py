"""Durable monitoring over recorded XProtect windows.

One SQLite table of assessments (a job per Watch, configuration version and recorded window). A job runs four stages
(read the recording, local vision, one Hafnia request, compare under the Watch policy). This samples recorded windows
at the Watch cadence; it is not real-time streaming. Every external effect sits behind an injectable runner.

Safeguards: a window is assessed once per Watch version (UNIQUE key); per-Watch and global daily Hafnia budgets; the
retention check runs before acquisition; a Hafnia request is claimed before it is sent and never resent after an
uncertain result; unfinished jobs are resumed after a restart; with no gateway session a job waits visibly.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading
import uuid

from adaptive_watch.assessment_job import StageError, Waiting, check_manifest, choose_interval, flag_loop, iso, parse, run_hafnia
from adaptive_watch.negative_review import read, sha
from ortru import policy

STAGES = [('acquisition', 'Read the recording from XProtect'), ('vision', 'Local vision'), ('hafnia', 'Ask Hafnia'),
          ('matching', 'Compare under the Watch policy')]
STATE_STAGE = dict(queued=0, acquiring=0, cv_running=1, hafnia_submitting=2, hafnia_waiting=2, matching=3)
TERMINAL = ('completed', 'failed')
WAITING_GATEWAY = ('Waiting for a Hafnia gateway session.',
                   'Start Ortru with scripts\\ortru.ps1 -Gateway and enter the gateway password once in that window. Nothing was sent.')
GLOBAL_PER_DAY = 60


class Engine:
    def __init__(self, root, watches, runner, gateway_factory=None, clock=None, global_per_day=GLOBAL_PER_DAY, resume=True):
        self.root, self.watches, self.runner = Path(root), watches, runner
        self.gateway_factory = gateway_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.global_per_day = global_per_day
        self.lock, self.threads = threading.RLock(), {}
        self.gpu = threading.Semaphore(1)  # one acquisition/vision at a time on the shared GPU host
        (self.root/'assessments').mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS assessments(id TEXT PRIMARY KEY, watch_id TEXT NOT NULL, version INTEGER NOT NULL, start TEXT NOT NULL,
                end TEXT NOT NULL, state TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}', failed_stage TEXT, error TEXT,
                resumable INTEGER NOT NULL DEFAULT 0, trigger TEXT NOT NULL DEFAULT 'schedule', created TEXT NOT NULL, updated TEXT NOT NULL,
                hafnia_at TEXT, UNIQUE(watch_id, version, start, end));
            CREATE TABLE IF NOT EXISTS checks(watch_id TEXT PRIMARY KEY, at TEXT NOT NULL, text TEXT NOT NULL);''')
        if resume:
            self.resume()

    # -- storage ------------------------------------------------------------------------------------
    def db(self):
        outer = self

        class C:
            def __enter__(s):
                s.d = sqlite3.connect(outer.root/'ortru.sqlite3', timeout=15, isolation_level=None)
                s.d.row_factory = sqlite3.Row
                return s.d

            def __exit__(s, *e):
                s.d.close()
        return C()

    def row(self, job_id):
        with self.db() as db:
            return db.execute('SELECT * FROM assessments WHERE id=?', (job_id,)).fetchone()

    def dir(self, job_id):
        return self.root/'assessments'/job_id

    def _set(self, job_id, **cols):
        cols['updated'] = self.clock().isoformat()
        with self.db() as db:
            db.execute('UPDATE assessments SET '+','.join(k+'=?' for k in cols)+' WHERE id=?', (*cols.values(), job_id))

    def _detail(self, job_id, stage, text, status=None):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            details = json.loads(db.execute('SELECT details FROM assessments WHERE id=?', (job_id,)).fetchone()[0])
            details[stage] = dict(detail=text, status=status)
            db.execute('UPDATE assessments SET details=? WHERE id=?', (json.dumps(details), job_id))
            db.execute('COMMIT')

    def _fail(self, job_id, stage, reason, next_step, resumable=False):
        self._detail(job_id, stage, reason, 'failed')
        self._set(job_id, state='failed', failed_stage=stage, error=json.dumps(dict(reason=reason, next=next_step)), resumable=int(resumable))

    def _note(self, watch_id, text):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO checks VALUES (?,?,?)', (watch_id, self.clock().isoformat(), text))

    # -- scheduling ---------------------------------------------------------------------------------
    def used_today(self, watch_id=None):
        since = (self.clock()-timedelta(hours=24)).isoformat()
        with self.db() as db:
            if watch_id:
                return db.execute('SELECT COUNT(*) FROM assessments WHERE hafnia_at>? AND watch_id=?', (since, watch_id)).fetchone()[0]
            return db.execute('SELECT COUNT(*) FROM assessments WHERE hafnia_at>?', (since,)).fetchone()[0]

    def schedule_view(self, watch):
        """Last completed assessment, next due time and why nothing is running, for the Watch screen."""
        wid = watch['id']
        with self.db() as db:
            last = db.execute("SELECT * FROM assessments WHERE watch_id=? ORDER BY created DESC LIMIT 1", (wid,)).fetchone()
            done = db.execute("SELECT id,created FROM assessments WHERE watch_id=? AND state='completed' ORDER BY created DESC LIMIT 1", (wid,)).fetchone()
            running = db.execute("SELECT id FROM assessments WHERE watch_id=? AND state NOT IN ('completed','failed') LIMIT 1", (wid,)).fetchone()
            check = db.execute('SELECT * FROM checks WHERE watch_id=?', (wid,)).fetchone()
        interval = watch['config']['schedule']['intervalMinutes']
        due = None
        if watch['status'] == 'active' and not running:  # one assessment at a time per Watch: the next starts after this one ends
            due = self.clock().isoformat() if last is None else (parse(last['created'])+timedelta(minutes=interval)).isoformat()
        return dict(status=watch['status'], intervalMinutes=interval, nextDue=due, runningJob=running['id'] if running else None,
                    lastAssessment=dict(id=done['id'], at=done['created']) if done else None,
                    lastJob=dict(id=last['id'], state=last['state'], at=last['created']) if last else None,
                    lastCheck=dict(at=check['at'], text=check['text']) if check else None,
                    usedToday=self.used_today(wid), budgetPerDay=watch['config']['quota']['perDay'],
                    globalUsedToday=self.used_today(), globalBudget=self.global_per_day)

    def tick(self):
        """Start any active Watch whose cadence is due. Safe to call repeatedly; returns the job ids started."""
        started = []
        for w in self.watches.list():
            if w['status'] != 'active':
                continue
            sched = self.schedule_view(w)
            if sched['runningJob'] or (sched['nextDue'] and parse(sched['nextDue']) > self.clock()):
                continue
            job = self.start(w['id'], trigger='schedule', quiet=True)
            if job and job['created']:
                started.append(job['id'])
        return started

    def start(self, watch_id, trigger='manual', quiet=False):
        """Pick the newest clean retained window for the Watch's camera and queue it, once.

        Returns dict(id, created) or None (quiet mode) / raises ValueError with the reason.
        """
        w = self.watches.get(watch_id)
        cfg = w['config']

        def refuse(text):
            self._note(watch_id, text)
            if quiet:
                return None
            raise ValueError(text)
        if w['status'] in ('disabled',) or (w['status'] != 'active' and trigger == 'schedule'):
            return refuse(f"The Watch is {w['status']}.")
        with self.lock:
            with self.db() as db:
                run = db.execute("SELECT id FROM assessments WHERE watch_id=? AND state NOT IN ('completed','failed')", (watch_id,)).fetchone()
            if run:
                return dict(id=run['id'], created=False)
            if self.used_today(watch_id) >= cfg['quota']['perDay']:
                return refuse(f"This Watch has used its budget of {cfg['quota']['perDay']} Hafnia requests in the last 24 hours.")
            if self.used_today() >= self.global_per_day:
                return refuse(f'All Watches together have used the limit of {self.global_per_day} Hafnia requests in the last 24 hours.')
            try:
                sequences = self.runner.sequences(cfg['camera']['name'])
                sched = cfg['schedule']
                start, end = choose_interval(sequences, self.clock(), phase=self.runner.phase(cfg, sequences, self.clock(), self.root),
                                             window=sched['windowSeconds'], margin=sched['marginSeconds'])
            except StageError as exc:
                return refuse(f'{exc.reason}. {exc.next}')
            except ValueError as exc:
                return refuse(str(exc))
            with self.db() as db:  # interval deduplication: any overlapping window of this Watch version counts as the same interval
                old = db.execute('SELECT id FROM assessments WHERE watch_id=? AND version=? AND start<? AND end>? ORDER BY created DESC',
                                 (watch_id, w['version'], end, start)).fetchone()
            if old:
                return refuse('This recorded window has already been assessed for this version of the Watch.') if quiet else dict(id=old['id'], created=False)
            job_id, now = uuid.uuid4().hex, self.clock().isoformat()
            with self.db() as db:
                db.execute('INSERT INTO assessments(id,watch_id,version,start,end,state,trigger,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                           (job_id, watch_id, w['version'], start, end, 'queued', trigger, now, now))
            d = self.dir(job_id)
            d.mkdir(parents=True, exist_ok=True)
            (d/'job.json').write_text(json.dumps(dict(id=job_id, watch=watch_id, version=w['version'], interval=[start, end], config=cfg), indent=2), encoding='utf-8')
            self._note(watch_id, f'Queued the recorded window {start} to {end}.')
            self._kick(job_id)
            return dict(id=job_id, created=True)

    # -- views --------------------------------------------------------------------------------------
    def get(self, job_id):
        r = self.row(job_id) if isinstance(job_id, str) else None
        if r is None:
            return None
        details, state = json.loads(r['details']), r['state']
        cur = len(STAGES) if state == 'completed' else STATE_STAGE.get(state)
        if state == 'failed':
            cur = [k for k, _ in STAGES].index(r['failed_stage'])
        stages = []
        for i, (key, label) in enumerate(STAGES):
            status = 'done' if i < cur else ('running' if i == cur else 'waiting')
            extra = details.get(key) or {}
            detail = extra.get('detail')
            if i == cur and state == 'failed':
                status = 'failed'
            if state in ('hafnia_submitting', 'hafnia_waiting') and i == cur and self.gateway_factory is None:
                status, detail = 'needs_you', ' '.join(WAITING_GATEWAY)
            stages.append(dict(key=key, label=label, status=status, **({'detail': detail} if detail else {})))
        if state == 'hafnia_waiting' and self.gateway_factory is not None:
            self._kick(job_id)
        return dict(id=r['id'], watchId=r['watch_id'], version=r['version'], state=state, trigger=r['trigger'], interval=[r['start'], r['end']],
                    stages=stages, error=json.loads(r['error']) if state == 'failed' else None, resumable=bool(r['resumable']),
                    created=r['created'], exceptionId=r['id'] if state == 'completed' else None)

    def jobs(self, watch_id=None, limit=30):
        with self.db() as db:
            rows = db.execute('SELECT id FROM assessments '+('WHERE watch_id=? ' if watch_id else '')+'ORDER BY created DESC LIMIT ?',
                              ((watch_id, limit) if watch_id else (limit,))).fetchall()
        return [self.get(r['id']) for r in rows]

    def wait(self, job_id, timeout=60):
        t = self.threads.get(job_id)
        if t:
            t.join(timeout)

    def retry(self, job_id):
        """Retry a failed job that never sent anything to Hafnia (a failed job with a Hafnia claim is never retried)."""
        r = self.row(job_id)
        if r is None or r['state'] != 'failed':
            raise ValueError('Only a failed assessment can be retried')
        if self._claims(job_id):
            raise ValueError('A Hafnia request already exists for this window, so it will not be sent again')
        with self.db() as db:
            db.execute("UPDATE assessments SET state='queued',failed_stage=NULL,error=NULL,resumable=0,details='{}' WHERE id=?", (job_id,))
        self._kick(job_id)
        return self.get(job_id)

    def discard(self, job_id):
        """Drop an assessment that is still waiting before Hafnia (nothing was sent). A job with a Hafnia claim is never discarded."""
        r = self.row(job_id)
        if r is None or r['state'] in TERMINAL:
            raise ValueError('Only an unfinished assessment can be discarded')
        if self._claims(job_id) or r['state'] == 'hafnia_waiting':
            raise ValueError('A Hafnia request already exists for this window, so this assessment cannot be discarded')
        self._fail(job_id, self._stage_of(r['state']), 'Discarded by you before it was sent to Hafnia', 'Assess the latest window to try again.')
        return self.get(job_id)

    # -- execution ----------------------------------------------------------------------------------
    def resume(self):
        with self.db() as db:
            rows = db.execute("SELECT id,state FROM assessments WHERE state NOT IN ('completed','failed') OR (state='failed' AND resumable=1)").fetchall()
        for r in rows:
            if r['state'] == 'failed':
                self._set(r['id'], state='hafnia_waiting', failed_stage=None, error=None, resumable=0)
            self._kick(r['id'])

    def _kick(self, job_id):
        with self.lock:
            t = self.threads.get(job_id)
            if t and t.is_alive():
                return
            t = self.threads[job_id] = threading.Thread(target=self._guard, args=(job_id,), daemon=True)
            t.start()

    def _claims(self, job_id):
        path = self.dir(job_id)/'hafnia'/'ledger.sqlite3'
        if not path.exists():
            return 0
        db = sqlite3.connect(path, timeout=15)
        try:
            return db.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
        finally:
            db.close()

    def _stage_of(self, state):
        return STAGES[STATE_STAGE.get(state, 3)][0]

    def _guard(self, job_id):
        try:
            self._advance(job_id)
        except Waiting:
            pass
        except StageError as exc:
            self._fail(job_id, self._stage_of(self.row(job_id)['state']), exc.reason, exc.next, exc.resumable)
        except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
            text = str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__
            self._fail(job_id, self._stage_of(self.row(job_id)['state']), f'This step stopped unexpectedly: {text}', 'Retry the assessment. If it repeats, check the server window.')
        except Exception as exc:  # never leave a job silently unfinished
            self._fail(job_id, self._stage_of(self.row(job_id)['state']), f'This step stopped unexpectedly ({type(exc).__name__}).',
                       'Retry the assessment. If it repeats, check the server window.')

    def _advance(self, job_id):
        while True:
            state = self.row(job_id)['state']
            if state in ('queued', 'acquiring'):
                with self.gpu:
                    self._record(job_id)
            elif state == 'cv_running':
                with self.gpu:
                    self._vision(job_id)
            elif state in ('hafnia_submitting', 'hafnia_waiting'):
                if not self._hafnia(job_id):
                    return
            elif state == 'matching':
                self._match(job_id)
            else:
                return
            if self.row(job_id)['state'] in TERMINAL:
                return

    def _job(self, job_id):
        return read(self.dir(job_id)/'job.json')

    def _record(self, job_id):
        r, d = self.row(job_id), self.dir(job_id)
        cfg = self._job(job_id)['config']
        cam = cfg['camera']
        self._set(job_id, state='acquiring')
        self._detail(job_id, 'acquisition', 'Checking the recording is still retained, then reading it (read only).')
        sequences = self.runner.sequences(cam['name'])  # retention check immediately before acquisition
        if not any(parse(s['start_utc']) <= parse(r['start']) and parse(r['end']) <= parse(s['end_utc']) for s in sequences):
            raise StageError('The recording has expired or is no longer retained', 'Choose a newer window; nothing was sent to Hafnia.')
        found = list((d/'acquisition').glob('*/manifest.json'))
        manifest = found[0] if found and 'mkv_export' in read(found[0]) else self.runner.acquire(cam['name'], r['start'], r['end'], d/'acquisition')
        m = check_manifest(manifest, cam['id'], r['start'], r['end'], camera=cam['name'])
        info, diffs = self.runner.encode(manifest, d/'media')
        times = [i/info['fps'] for i in range(len(diffs)+1)]
        (d/'frame-diffs.json').write_text(json.dumps(dict(times=times, diffs=diffs)), encoding='utf-8')
        (d/'job.json').write_text(json.dumps(self._job(job_id) | dict(manifest=str(manifest.relative_to(d)).replace('\\', '/'))), encoding='utf-8')
        verify = getattr(self.runner, 'verify_loop', None)
        window = verify(cfg, manifest, r['start'], self.root) if verify else None
        if window is not None:
            (d/'loop-window.json').write_text(json.dumps(window), encoding='utf-8')
            if not window.get('ok'):
                (self.root/'loops'/f"{cam['id'].lower()}-reference.json").unlink(missing_ok=True)  # measure the loop again next time
                raise StageError('The recording does not follow the expected loop timing', 'Ortru will measure the loop again; nothing was sent to Hafnia.')
        check = flag_loop(diffs, times)
        (d/'loop-check.json').write_text(json.dumps(check), encoding='utf-8')
        if check['flagged']:
            raise StageError('The recording appears to restart partway through (the camera replays a short loop)',
                             'Ortru will pick a different window next time; nothing was sent to Hafnia.')
        (d/'continuity.json').write_text(json.dumps(dict(manifest_sha256=sha(manifest), reviewed_at=self.clock().isoformat(),
                                                         reviewer='automatic frame-difference check (no operator confirmation)', check=check)), encoding='utf-8')
        self._detail(job_id, 'acquisition', f"{len(m['frames'])} snapshots and a {info['duration']:.1f} s video saved. No restart detected in the recording.")
        self._set(job_id, state='cv_running')

    def _vision(self, job_id):
        d, job = self.dir(job_id), self._job(job_id)
        cfg = job['config']
        manifest = d/job['manifest']
        self._detail(job_id, 'vision', f"Running {cfg['detector']['id'].replace('_', ' ')} on the Linux GPU.")
        (d/'zone.json').write_text(json.dumps(dict(id=job['id'], polygon=cfg['region']['polygon'])), encoding='utf-8')
        out = d/'cv.json'
        if not out.exists():
            self.runner.run_cv(manifest, d/'zone.json', out)
        cv, m = read(out), read(manifest)
        if cv.get('manifest_sha256') != sha(manifest) or len(cv.get('observations', [])) != len(m['frames']):
            out.unlink()
            raise StageError('The vision output does not match this recording', 'Retry the assessment.')
        self._detail(job_id, 'vision', f"{cv['device']}: {cv['frames']} frames in {cv['processing_s']:.1f} s, {len(cv['tracks'])} person tracks.")
        self._set(job_id, state='hafnia_submitting')

    def _hafnia(self, job_id):
        """True when the answer is saved. Without a gateway session nothing is called and the job waits."""
        if self.gateway_factory is None:
            return False
        d, r, job = self.dir(job_id), self.row(job_id), self._job(job_id)
        cfg = job['config']
        entry = dict(scene=cfg['name'], camera_id=cfg['camera']['id'], start=r['start'], end=r['end'], prompt=cfg['hafnia']['prompt'],
                     prompt_version='watch-'+str(job['version']), continuity_review='no_loop_boundary',
                     recording_manifest=str((d/job['manifest']).resolve()))
        if read(d/'continuity.json')['manifest_sha256'] != sha(d/job['manifest']):
            raise StageError('The recording changed after the continuity check', 'Retry the assessment.')
        self._detail(job_id, 'hafnia', 'Sending one request to Hafnia, or reading the answer to the one already sent.')
        if not self._claims(job_id) and not r['hafnia_at']:
            self._set(job_id, hafnia_at=self.clock().isoformat())  # counts against the budgets from the moment it is attempted

        def on_state(state):
            self._set(job_id, state=state)
            self._detail(job_id, 'hafnia', 'Request sent once. Waiting for the answer.' if state == 'hafnia_waiting' else 'Sending one request to Hafnia.')
        record = self.runner.hafnia(d, entry, self.gateway_factory, on_state)
        (d/'hafnia.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        self._detail(job_id, 'hafnia', 'Hafnia answered: '+str(record['parsed'].get('outcome', 'no usable answer')).replace('_', ' ')+'.')
        self._set(job_id, state='matching')
        return True

    def _match(self, job_id):
        from ortru.exceptions import build_view
        d, job = self.dir(job_id), self._job(job_id)
        manifest = d/job['manifest']
        m = read(manifest)
        paths = [manifest, d/'job.json', d/'continuity.json', d/'cv.json', d/'hafnia.json', d/'media/media.json', d/'media/original.mp4',
                 manifest.parent/m['mkv_export']['file'], *[manifest.parent/f['file'] for f in m['frames']]]
        (d/'sources.json').write_text(json.dumps([dict(path=str(p.relative_to(d)).replace('\\', '/'), sha256=sha(p)) for p in paths], indent=2), encoding='utf-8')
        view = build_view(self, job_id)
        self._detail(job_id, 'matching', view['policy']['label']+('. Raised as an exception.' if view['policy']['raised'] else '. No exception raised.'))
        self._set(job_id, state='completed')
