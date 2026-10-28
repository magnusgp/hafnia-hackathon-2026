"""One operator-facing view model for every saved assessment.

Wraps the existing source-verified stores (railway review store, workspace cases). Adds the
agent-review ledger and native-handoff state. Never sends, configures, or infers anything.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from adaptive_watch import assessment_job as live
from adaptive_watch.negative_review import Conflict, ReviewStore, digest, read, sha
from adaptive_watch.workspace import Workspace, CASES

DISPLAY = dict(railway='Station platform', gate='School gate at night', scooter='Sidewalk with scooter', bin='Sidewalk with bin')
PURPOSE = dict(
    railway='Hafnia answered no entry. Independent person detection had the same person at the platform edge first.',
    gate='Two Hafnia prompts disagree about the gate being handled and opened. No local vision or original video is saved for this case.',
    scooter='Local vision measured how long the scooter stayed still. Hafnia agreed it was left there.',
    bin='Local vision measured how long the bin stayed still. Hafnia agreed it was left there.')
NATIVE_EVENT = 'Adaptive Watch Review Required'
HAFNIA_HEAD = dict(gate='Negative: no opening observed', scooter='Supports a left object', bin='Supports a left object')
HANDOFF_TEXT = ('Review exception: Hafnia reported no entry; independent person detection placed a person at the '
                'platform edge from {trigger} UTC. Neither signal confirms entry. Review the footage.')
REVIEWERS = {'Claude demo reviewer'}


def clock_tenths(timestamp):
    """HH:MM:SS.s (UTC) from an ISO timestamp, always one decimal."""
    t = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(timezone.utc)
    return f'{t:%H:%M:%S}.{t.microsecond // 100000}'


def agent_review_table(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS agent_reviews(id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, at TEXT NOT NULL,
        source_revision TEXT NOT NULL, document TEXT NOT NULL);
      CREATE TRIGGER IF NOT EXISTS agent_no_update BEFORE UPDATE ON agent_reviews BEGIN SELECT RAISE(ABORT,'append only'); END;
      CREATE TRIGGER IF NOT EXISTS agent_no_delete BEFORE DELETE ON agent_reviews BEGIN SELECT RAISE(ABORT,'append only'); END;
    ''')


class Casebook:
    def __init__(self, repo, root, railway, evaluations, release):
        self.repo, self.root, self.railway, self.evaluations, self.release = map(Path, (repo, root, railway, evaluations, release))
        self.live_root = self.root/'live'
        self.ws = Workspace(self.repo, self.root, self.railway, self.evaluations)
        agent_review_table(self.ws.db)
        self.ws.db.commit()

    def close(self):
        self.ws.close()

    # -- agent review ledger ------------------------------------------------
    def record_agent_review(self, case_id, document, source_revision):
        if case_id not in CASES:
            raise KeyError(case_id)
        if document.get('reviewer') not in REVIEWERS or 'not a human' not in document.get('provenance', ''):
            raise ValueError('Agent reviews must carry explicit AI provenance')
        with self.ws.db:
            self.ws.db.execute('INSERT INTO agent_reviews(case_id,at,source_revision,document) VALUES (?,?,?,?)',
                               (case_id, datetime.now(timezone.utc).isoformat(), source_revision, json.dumps(document)))

    def agent_review(self, case_id, source_revision):
        row = self.ws.db.execute('SELECT source_revision,document FROM agent_reviews WHERE case_id=? ORDER BY id DESC LIMIT 1',
                                 (case_id,)).fetchone()
        if not row:
            return None
        review = json.loads(row[1])
        review['currentSource'] = row[0] == source_revision  # a review of changed evidence is not shown as current
        return review

    # -- native handoff -----------------------------------------------------
    def native(self, case_id):
        """Planned / configured / sent / alarm-verified, kept apart. Read-only."""
        state = dict(eventName=NATIVE_EVENT, state='not_configured', alarmId=None,
                     detail='The review event and its camera alarm have not been set up in XProtect.')
        config = self.release/'native'/'config.json'
        if config.exists() and read(config).get('railway', {}).get('configured') is True:
            state.update(state='configured', detail='The review event and its camera alarm exist in XProtect. Nothing has been sent.')
        proof = self.root/'native'/'status.json'  # per application instance, so demo and real runs never share send state
        if proof.exists():
            mine = read(proof).get(case_id)
            if mine:
                state.update(mine)
        return state

    # -- views ----------------------------------------------------------------
    def railway_view(self):
        store = ReviewStore(self.railway)
        try:
            v = store.view()
            record, _ = store.verified()
        finally:
            store.close()
        media = read(self.release/'media/railway/media.json')
        if media['sourceMkvSha256'] != sha(Path(record['originalVideo'])):
            raise ValueError('Browser video does not derive from the verified original')
        times = {s['index']: s['mediaTime'] for s in media['samples']}
        frames = [dict(index=f['index'], timestamp=f['timestamp'], mediaTime=times[f['index']], box=f['box'],
                       distance=f['distance'], near=f['proximity'], file=f"/api/cases/railway/frames/{f['index']}")
                  for f in v['frames']]
        trigger = next((f for f in frames if f['near']), None)
        revision = digest([v['revision'], media['sha256']])
        return dict(
            id='railway', flagship=True, title=DISPLAY['railway'], camera=v['camera'], interval=v['interval'],
            purpose=PURPOSE['railway'], revision=revision, actionRevision=v['revision'], kind='video', frames=frames,
            video=dict(url='/api/cases/railway/video', duration=media['duration'], fps=media['fps'],
                       origin=media['samples'][0]['timestamp'], sha256=media['sha256']),
            hafnia=dict(answer='No entry observed', verdict='negative', quote=v['hafnia']['conclusion'],
                        summaryId=v['hafnia']['summaryId'], request=v['hafnia']['originalRequest']['Prompt']),
            vision=dict(label='Person detector, Linux A10G', model=v['cv']['model'], trackId=7, region=v['state']['region'],
                        trigger=trigger, regionStatus='draft region, reviewed against the footage', samplesPerSecond=2,
                        meaning='The person was at the platform edge. This asks for a look. It does not say they entered.'),
            handoff=dict(event=NATIVE_EVENT, camera=DISPLAY['railway'], window=v['interval'],
                         message=HANDOFF_TEXT.format(trigger=clock_tenths(trigger['timestamp']) if trigger else 'n/a'),
                         alarm='Adaptive Watch review: station platform'),
            agent=self.agent_review('railway', revision), state=v['state'], native=self.native('railway'),
            diagnostic=dict(v['diagnostic']), provenance=dict(hashes=v['evidenceHashes'], reference=v['reference']),
            limitations=[v['cv']['limitation']])

    def other_view(self, case_id):
        v = self.ws.view(case_id)
        frames = [dict(index=f['index'], timestamp=f['timestamp'], mediaTime=None, box=f['box'], near=False,
                       file=f['file']) for f in v['frames']]
        vision = None
        if v.get('model'):
            vision = dict(label='Object tracker, Linux A10G', model=v['model'], region=v.get('polygon'),
                          runs=v['runs'], meaning=v['evidence'])
        answers = [dict(summaryId=h['summary_id'], quote=h['original_response'], parsed=h['parsed']['outcome'],
                        prompt=h['request']['Prompt']) for h in v['hafnia']]
        revision = v['revision']
        return dict(id=case_id, flagship=False, title=DISPLAY[case_id], camera=v['camera'], interval=v['interval'],
                    purpose=PURPOSE[case_id], revision=revision, actionRevision=revision, kind='snapshots', frames=frames, video=None,
                    hafnia=dict(answer=HAFNIA_HEAD[case_id], answers=answers, quote=v['summary']), vision=vision,
                    agent=self.agent_review(case_id, revision), state=v['state'], native=self.native(case_id),
                    diagnostic=v.get('diagnostic'), limitations=v['limitations'],
                    provenance=dict(interval=v['interval']))

    # -- live (browser-started) assessments; state is per case id in the workspace db ---------------
    def live_native(self, case_id):
        """The camera's event and alarm exist; send state is read per live case, never borrowed from another case."""
        state = live.default_native()
        config = self.release/'native'/'config.json'
        if config.exists() and read(config).get('railway', {}).get('configured') is True:
            state.update(state='configured', detail='Event and camera alarm exist in XProtect. Nothing has been sent for this assessment.')
        proof = self.root/'native'/'status.json'
        if proof.exists() and read(proof).get(case_id):
            state.update(read(proof)[case_id])
        return state

    def live_job(self, case_id):
        return live.resolve_case(self.live_root, case_id)

    def live_state(self, case_id, job_id):
        row = self.ws.db.execute('SELECT state FROM reviews WHERE case_id=?', (case_id,)).fetchone()
        return json.loads(row[0]) if row else live.initial_state(self.live_root/job_id)

    def live_view(self, case_id):
        job_id = self.live_job(case_id)
        return live.live_case(self.live_root, job_id, self.live_state(case_id, job_id), self.live_native(case_id))

    def live_files(self, case_id):
        return live.case_files(self.live_root, self.live_job(case_id))

    def act_live(self, case_id, body):
        job_id = self.live_job(case_id)
        self.ws.db.execute('BEGIN IMMEDIATE')
        try:
            view = self.live_view(case_id)
            if body.get('revision') != view['actionRevision']:
                raise Conflict('Evidence or review changed; reload before deciding')
            state = live.apply_action(view['state'], body, view['vision']['trigger'])
            self.ws.db.execute('INSERT INTO reviews VALUES (?,?) ON CONFLICT(case_id) DO UPDATE SET state=excluded.state',
                               (case_id, json.dumps(state)))
            self.ws.db.execute('INSERT INTO review_audit(case_id,at,document) VALUES (?,?,?)',
                               (case_id, datetime.now(timezone.utc).isoformat(),
                                json.dumps(dict(action=body.get('action'), revision=view['actionRevision'], state=state))))
            self.ws.db.commit()
        except Exception:
            self.ws.db.rollback()
            raise
        return self.live_view(case_id)

    def view(self, case_id):
        if case_id.startswith('live-'):
            return self.live_view(case_id)
        if case_id not in CASES:
            raise KeyError(case_id)
        return self.railway_view() if case_id == 'railway' else self.other_view(case_id)

    def index(self):
        cases, unavailable = [], []
        for case_id in CASES:
            try:
                v = self.view(case_id)
                cases.append({k: v[k] for k in ('id', 'flagship', 'title', 'purpose', 'interval', 'kind')}
                             | dict(status=self.status(v)))
            except (ValueError, TypeError, KeyError, OSError, sqlite3.Error, StopIteration):
                unavailable.append(dict(id=case_id, title=DISPLAY[case_id],
                                        error='Source files failed verification. Restore the original recording, response and vision output.'))
        for job_id in reversed(live.completed_jobs(self.live_root)):
            case_id = 'live-'+job_id[:8]
            try:
                v = self.live_view(case_id)
                cases.append({k: v[k] for k in ('id', 'flagship', 'title', 'purpose', 'interval', 'kind')}
                             | dict(status=self.status(v) if v['state'].get('status') != 'review_required'
                                    else ('Needs review' if v['vision']['trigger'] else 'Evidence')))
            except (ValueError, TypeError, KeyError, OSError, sqlite3.Error, StopIteration):
                unavailable.append(dict(id=case_id, title=live.TITLE, error=live.EVIDENCE_LOST))
        return dict(cases=cases, unavailable=unavailable)

    @staticmethod
    def status(v):
        if v['native']['state'] == 'alarm_verified':
            return 'In XProtect'
        if v['state'].get('status') in {'xprotect_review_requested', 'review_request_saved'}:
            return 'Review saved'
        if v['state'].get('status') == 'dismissed':
            return 'Dismissed'
        return 'Needs review' if v['flagship'] else 'Evidence'
