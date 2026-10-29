"""Exceptions: the real assessments that met a Watch's attention policy, built only from verified job files.

An assessment is evidence (recording, vision output, Hafnia answer, hashes). An Exception is that assessment when the
Watch policy raises it. The local review decision is stored apart from the evidence and from the native dispatch.
"""
from datetime import datetime, timezone
import json
import sqlite3

from adaptive_watch.assessment_job import hms, verified_sources
from adaptive_watch.negative_review import digest, distance, read
from adaptive_watch.tracking import foot
from ortru import SCHEMA, policy

VERDICTS = ('visible', 'not_visible', 'unclear')
OUTCOMES = ('escalate', 'dismiss', 'confirm_local')
REVIEWERS = dict(operator='Local operator (identity not authenticated)', claude_ai_demo='Claude, AI demo reviewer (not a human)')


class Stale(ValueError):
    """The decision changed since this screen loaded."""


def question(condition):
    return f'Is "{condition}" visible in the footage?'


def answer_options(condition):
    return [dict(id='visible', label=f'{condition}: yes'), dict(id='not_visible', label=f'{condition}: no'),
            dict(id='unclear', label="Can't tell from the footage")]


def vision_samples(cv, manifest, media, region, margin):
    polygon = region['polygon']
    times = {s['index']: s['mediaTime'] for s in media['samples']}
    dist = [{o['track_id']: (distance(foot(o['box']), polygon), o['box']) for o in obs['objects']} for obs in cv['observations']]
    first = min(((i, t) for i, row in enumerate(dist) for t, (d, _) in row.items() if d <= margin), default=None)
    selected = first[1] if first else None
    samples = []
    for i, f in enumerate(manifest['frames']):
        d, box = dist[i].get(selected, (None, None))
        samples.append(dict(index=i, timestamp=f['timestamp_utc'], mediaTime=times[i], box=box, distance=d, near=d is not None and d <= margin))
    return selected, samples


def reason_text(kind, condition, at):
    when = f' from {at} UTC' if at else ''
    return {
        'disagreement': f'Hafnia did not observe "{condition}". Person detection had a person at the region{when}.',
        'corroborated': f'Hafnia reported "{condition}" and person detection had a person at the region{when}.',
        'unresolved': f'Hafnia could not give a usable answer. Person detection had a person at the region{when}.',
        'hafnia_only': f'Hafnia reported "{condition}" but person detection saw no one at the region.',
        'clear': 'Neither source found anything.',
        'inconclusive': 'Hafnia gave no usable answer and person detection saw no one at the region.'}[kind]


def build_view(engine, job_id, decision=None, native=None):
    """The one representation of a completed assessment. Raises ValueError if any source file fails verification."""
    d = engine.dir(job_id)
    sources = verified_sources(d)
    job = read(d/'job.json')
    cfg = job['config']
    m, cv, media, record = read(d/job['manifest']), read(d/'cv.json'), read(d/'media/media.json'), read(d/'hafnia.json')
    margin = cfg['detector']['parameters'].get('margin', 0)
    if (len(cv['observations']) != len(m['frames']) or media['sourceMkvSha256'] != m['mkv_export']['sha256']
            or any(o['timestamp_utc'] != f['timestamp_utc'] for o, f in zip(cv['observations'], m['frames']))):
        raise ValueError('Vision output or video does not derive from the verified recording')
    selected, samples = vision_samples(cv, m, media, cfg['region'], margin)
    trigger = next((s for s in samples if s['near']), None)
    h_out = policy.hafnia_outcome(record)
    verdict = policy.decide(h_out, 'triggered' if trigger else 'none', cfg['policy']['raiseOn'])
    parsed, summary = record['parsed'], record['summary']
    valid = parsed.get('category') == 'valid_model_decision'
    at = hms(trigger['timestamp']) if trigger else None
    condition = cfg['hafnia']['condition']
    reason = reason_text(verdict['kind'], condition, at)
    answer, tone = dict(observed=('Observed', 'positive'), not_observed=('Not observed', 'negative'), uncertain=('Unsure', 'uncertain'),
                        malformed=('No usable answer', 'uncertain'))[h_out]
    eid = job_id
    rev_basis = digest([eid, digest(sources), decision and decision['revision']])
    camera_name = cfg['camera']['name']
    return dict(
        schema=SCHEMA, id=eid, kind='live', raised=verdict['raised'], revision=rev_basis,
        watch=dict(id=job['watch'], version=job['version'], name=cfg['name']),
        camera=dict(id=cfg['camera']['id'], name=camera_name), interval=job['interval'], at=trigger['timestamp'] if trigger else job['interval'][0],
        policy=dict(kind=verdict['kind'], raised=verdict['raised'], label=verdict['label'], raiseOn=cfg['policy']['raiseOn']),
        reason=reason,
        hafnia=dict(answer=answer, outcome=h_out, tone=tone, quote=(parsed.get('evidence') if valid else str(parsed.get('reason') or summary.get('Response') or '')[:600]),
                    timing=parsed.get('timing') if valid else None, limitations=parsed.get('limitations') if valid else None,
                    summaryId=summary.get('Id'), prompt=record['request']['Prompt'], source='Hafnia VLM (AI footage review)'),
        vision=dict(detector=cfg['detector']['id'], parameters=cfg['detector']['parameters'], device=cv['device'], model=cv['model'],
                    region=cfg['region'], samples=samples, trackId=selected, trigger=trigger, samplesPerSecond=2, tracks=len(cv['tracks']),
                    meaning='A tracked person was at the region at a sampled moment. This is proximity, not confirmed entry.' if trigger
                    else 'No detected person reached the region. Detection can miss people.'),
        video=dict(url=f'/api/exceptions/{eid}/video', duration=media['duration'], fps=media['fps'], origin=media['samples'][0]['timestamp'], sha256=media['sha256']),
        frames=[dict(index=s['index'], url=f"/api/exceptions/{eid}/frames/{s['index']}") for s in samples],
        review=dict(question=question(condition), options=answer_options(condition), condition=condition,
                    outcomes=outcomes_for(cfg, verdict['raised'])),
        handoff=handoff(cfg, camera_name, reason, trigger, job['interval']) if verdict['raised'] and trigger else None,
        decision=decision, native=native,
        provenance=dict(hashes=[dict(name=s['path'].split('/')[-1], path=s['path'], sha256=s['sha256']) for s in sources],
                        watchConfig=cfg, hafniaRequestSha256=record.get('request_sha256'),
                        continuity=read(d/'continuity.json').get('reviewer'),
                        human=('Reviewed by '+REVIEWERS[decision['reviewer']]+'. ' if decision and decision.get('reviewer') == 'claude_ai_demo' else
                               'Review decisions are by the local operator; identity is not authenticated. ')
                        + 'Hafnia is an AI footage review, not a human one.'),
        limitations=['Person tracks are association hypotheses; identities can switch and detections can be missed.',
                     'Hafnia answered the Watch instruction once. Its answer is a model assessment, not a verified fact.',
                     'The region was drawn on a snapshot and is not calibrated to real-world distances.'])


def outcomes_for(cfg, raised):
    out = [dict(id='dismiss', label='Dismiss')]
    if raised:
        out.append(dict(id='escalate', label='Send to XProtect', enabled=bool(cfg['native']['alarm']),
                        why=None if cfg['native']['alarm'] else 'No XProtect alarm is set up for this Watch. Open the Watch to see what is missing.'))
        out.append(dict(id='confirm_local', label='Confirm, no alert'))
    return out


def handoff(cfg, camera_name, reason, trigger, interval):
    return dict(event=cfg['native']['event'], alarm=cfg['native']['alarm'], camera=camera_name, window=interval,
                message=f'Review request: {reason} Camera {camera_name}. Review the footage.')


class Reviews:
    """Local decisions, one row per exception, with a revision counter. Never touches evidence or the native ledger."""
    def __init__(self, engine):
        self.engine = engine
        with engine.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS decisions(exception_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL,
                verdict TEXT, note TEXT, outcome TEXT, watched INTEGER NOT NULL, at TEXT NOT NULL)''')
            if 'reviewer' not in [c[1] for c in db.execute('PRAGMA table_info(decisions)')]:
                db.execute("ALTER TABLE decisions ADD COLUMN reviewer TEXT NOT NULL DEFAULT 'operator'")

    def get(self, exception_id):
        with self.engine.db() as db:
            r = db.execute('SELECT * FROM decisions WHERE exception_id=?', (exception_id,)).fetchone()
        if r is None:
            return dict(revision=0, status='undecided', verdict=None, note='', outcome=None, at=None, reviewer=None)
        return dict(revision=r['revision'], status=r['status'], verdict=r['verdict'], note=r['note'], outcome=r['outcome'], at=r['at'],
                    reviewer=r['reviewer'], reviewerLabel=REVIEWERS.get(r['reviewer']))

    def decide(self, exception_id, body, view):
        if not isinstance(body, dict):
            raise ValueError('Expected a decision')
        if body.get('expectedRevision') != self.get(exception_id)['revision']:
            raise Stale('This exception was decided elsewhere. Reload to see the latest decision.')
        outcome, verdict, note = body.get('outcome'), body.get('verdict'), str(body.get('note', '')).strip()
        if outcome not in OUTCOMES or verdict not in VERDICTS:
            raise ValueError('Choose what you see and what to do')
        if body.get('watchedFootage') is not True:
            raise ValueError('Confirm that you watched the relevant footage')
        if len(note) > 1000:
            raise ValueError('The note is too long')
        reviewer = body.get('reviewer', 'operator')
        if reviewer not in REVIEWERS:
            raise ValueError('Unknown reviewer')
        if outcome != 'dismiss' and not view['raised']:
            raise ValueError('This assessment did not raise an exception')
        opt = next(o for o in view['review']['outcomes'] if o['id'] == outcome)
        if opt.get('enabled') is False:
            raise ValueError(opt['why'])
        if verdict != 'unclear' and not note:
            raise ValueError('Add a short note about what the footage shows')
        status = dict(escalate='review_requested', dismiss='dismissed', confirm_local='confirmed')[outcome]
        with self.engine.db() as db:
            db.execute('BEGIN IMMEDIATE')
            r = db.execute('SELECT revision FROM decisions WHERE exception_id=?', (exception_id,)).fetchone()
            if (r['revision'] if r else 0) != body['expectedRevision']:
                db.execute('ROLLBACK')
                raise Stale('This exception was decided elsewhere. Reload to see the latest decision.')
            db.execute('INSERT OR REPLACE INTO decisions(exception_id,revision,status,verdict,note,outcome,watched,at,reviewer) VALUES (?,?,?,?,?,?,?,?,?)',
                       (exception_id, body['expectedRevision']+1, status, verdict, note, outcome, 1, datetime.now(timezone.utc).isoformat(), reviewer))
            db.execute('COMMIT')
        return self.get(exception_id)
