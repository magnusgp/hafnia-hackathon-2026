"""Durable conservative episode grouping. No native network or dispatch capability."""
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, episode TEXT NOT NULL, document TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY, state TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assessments(id TEXT PRIMARY KEY, observation TEXT NOT NULL, document TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, episode TEXT NOT NULL, at TEXT NOT NULL, document TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS approval_requests(id TEXT PRIMARY KEY, episode TEXT NOT NULL, decision TEXT NOT NULL, document TEXT NOT NULL);
    ''')
    db.executescript("""
    CREATE TABLE IF NOT EXISTS native_dispatches(episode TEXT PRIMARY KEY, document TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions BEGIN SELECT RAISE(ABORT,'append only'); END;
    CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions BEGIN SELECT RAISE(ABORT,'append only'); END;
    """)
    db.commit()


def compatible(a, b):
    if any(a[k] != b[k] for k in ('cameraGuid', 'capability', 'objectClass')):
        return False
    if a.get('conflict') or b.get('conflict'):
        return False
    hashes = [[f.get('sha256') for f in x['frames']] for x in (a,b)]
    if hashes[0] and all(hashes[0]) and hashes[0] == hashes[1]:
        return a.get('location') == b.get('location')
    # Exact recording identity is repeat evidence, even after a synthetic reset.
    if a['manifestSha256'] == b['manifestSha256']:
        return a.get('location') == b.get('location') and a['interval'] == b['interval']
    if a.get('loopReset') or b.get('loopReset'):
        return False
    if not a['geometryApproved'] or not b['geometryApproved'] or a['polygon'] != b['polygon']:
        return False
    boxes = [x.get('location') for x in (a, b)]
    if any(x is None for x in boxes) or max(abs(x-y) for x,y in zip(*boxes)) > .025:
        return False
    bounds = [[datetime.fromisoformat(t.replace('Z','+00:00')).timestamp() for t in x['interval']] for x in (a,b)]
    return max(bounds[0][0], bounds[1][0]) - min(bounds[0][1], bounds[1][1]) <= 1.5


def ingest(db, document):
    d = dict(document)
    d.setdefault('objectClass', d['camera'])  # camera registry defines a single compatible query family
    d.setdefault('location', next((f['box'] for f in d['frames'] if f.get('box')), None))
    identity_parts = [d['cameraGuid'], d['capability'], d['manifestSha256'], d['cvSha256'], d['interval']]
    if d.get('evidenceKind') == 'replay':
        if not d.get('syntheticFixture') or d.get('dispatchReviewReady'):
            raise ValueError('Replay must be synthetic and cannot be dispatch ready')
        identity_parts.append(['replay', d['replayArrivalId']])
    identity = digest(identity_parts)[:24]
    db.execute('BEGIN IMMEDIATE')
    try:
        previous = db.execute('SELECT episode FROM observations WHERE id=?', (identity,)).fetchone()
        if previous:
            episode = previous[0]
        else:
            matches = set()
            for eid,state in db.execute('SELECT id,state FROM episodes'):
                if state in ('dismissed','escalated') and d.get('evidenceKind') != 'replay':
                    continue
                prior = [json.loads(raw) for (raw,) in db.execute('SELECT document FROM observations WHERE episode=?',(eid,))]
                prior.sort(key=lambda x:x['interval'][0])
                supporting = [x for x in prior if x.get('independentEvidence',True)] or prior[:1]
                anchor = supporting[0].get('location')
                location = d.get('location')
                stable = anchor is not None and location is not None and max(abs(x-y) for x,y in zip(anchor,location)) <= .025
                exact_repeat = any(d['manifestSha256'] == x['manifestSha256'] and d['interval'] == x['interval'] and d.get('location') == x.get('location') for x in prior)
                content = [f.get('sha256') for f in d['frames']]
                replay = bool(content) and all(content) and any(content == [f.get('sha256') for f in x['frames']] and d.get('location') == x.get('location') for x in prior)
                no_conflict = not d.get('conflict') and not any(x.get('conflict') for x in prior)
                same_family = all(d[k] == prior[0][k] for k in ('cameraGuid','capability','objectClass'))
                terminal_repeat = state not in ('dismissed','escalated') or all(x.get('evidenceKind') == 'replay' for x in prior) and (exact_repeat or replay)
                if terminal_repeat and no_conflict and same_family and (exact_repeat or replay or stable and compatible(d,supporting[-1])):
                    matches.add(eid)
            # Ambiguous multiple matches never silently merge distinct incidents.
            episode = next(iter(matches)) if len(matches) == 1 else uuid4().hex[:24]
            db.execute('INSERT OR IGNORE INTO episodes VALUES (?,?)',(episode,'candidate'))
            d['independentEvidence'] = not d.get('loopReset',False)
            for (raw,) in db.execute('SELECT document FROM observations WHERE episode=?',(episode,)):
                prior = json.loads(raw)
                hashes = [[f.get('sha256') for f in x['frames']] for x in (d,prior)]
                if hashes[0] and all(hashes[0]) and hashes[0] == hashes[1]:
                    d['independentEvidence'] = False
            db.execute('INSERT INTO observations VALUES (?,?,?)',(identity,episode,json.dumps(d)))
        for assessment in d['hafnia']:
            assessment = dict(assessment, joinedSha256=d['joinedSha256'])
            aid = digest([identity, assessment])
            db.execute('INSERT OR IGNORE INTO assessments VALUES (?,?,?)',(aid,identity,json.dumps(assessment)))
        db.commit()
        return episode
    except Exception:
        db.rollback()
        raise


def view(db, episode):
    row = db.execute('SELECT state FROM episodes WHERE id=?',(episode,)).fetchone()
    if not row:
        raise KeyError(episode)
    observations = [dict(json.loads(raw), observationId=oid) for oid,raw in db.execute('SELECT id,document FROM observations WHERE episode=? ORDER BY id',(episode,))]
    observations.sort(key=lambda d:d['interval'][0])
    d = dict(observations[-1], id=episode, state=row[0], status=row[0].replace('_',' '))
    supporting = [o for o in observations if o.get('independentEvidence',True)] or observations[:1]
    d['interval'] = [min(o['interval'][0] for o in supporting),max(o['interval'][1] for o in supporting)]
    d['independentObservationCount'] = len([o for o in observations if o.get('independentEvidence',True)])
    d['observations'] = observations
    d['observationCount'] = len(observations)
    d['hafnia'] = [json.loads(raw) for (raw,) in db.execute('SELECT document FROM assessments WHERE observation IN (SELECT id FROM observations WHERE episode=?) ORDER BY id',(episode,))]
    d['decisions'] = [json.loads(raw) for (raw,) in db.execute('SELECT document FROM decisions WHERE episode=? ORDER BY at,id',(episode,))]
    d['approvalRequests'] = [json.loads(raw) for (raw,) in db.execute('SELECT document FROM approval_requests WHERE episode=?',(episode,))]
    d['operatorAction'] = 'Review evidence' if row[0] == 'candidate' else 'View review'
    return d


def decide(db, episode, action, note='', evidence=None):
    targets = {'review_required':'review_required','dismiss':'dismissed','request_escalation':'review_required','resolution_unverified':'resolution_unverified'}
    if action not in targets or not isinstance(note,str) or len(note)>4000:
        raise ValueError('Invalid decision')
    db.execute('BEGIN IMMEDIATE')
    try:
        d = view(db,episode)
        if db.execute('SELECT 1 FROM native_dispatches WHERE episode=?',(episode,)).fetchone():
            raise ValueError('Native dispatch reserved; reconcile through guarded CLI')
        if d['state'] in ('dismissed','escalated'):
            raise ValueError('Terminal episode requires a new reviewed observation')
        ids = sorted(o['observationId'] for o in d['observations'])
        if evidence != ids:
            raise ValueError('Evidence changed; reload before deciding')
        event = dict(id=uuid4().hex,episode=episode,action=action,note=note,at=datetime.now(timezone.utc).isoformat(),evidence=ids,
                     evidenceHashes=sorted({o['joinedSha256'] for o in d['observations']} | {h.get('joinedSha256', d['joinedSha256']) for h in d['hafnia']}),
                     assessments=[h for h in d['hafnia']])
        db.execute('INSERT INTO decisions VALUES (?,?,?,?)',(event['id'],episode,event['at'],json.dumps(event)))
        db.execute('UPDATE episodes SET state=? WHERE id=?',(targets[action],episode))
        if action == 'request_escalation':
            request = dict(id=uuid4().hex,episode=episode,decision=event['id'],state='pending_human_dispatch_approval',evidence=ids,revision=digest([ids,d['hafnia']]))
            db.execute('INSERT INTO approval_requests VALUES (?,?,?,?)',(request['id'],episode,event['id'],json.dumps(request)))
        db.commit()
        return view(db,episode)
    except Exception:
        db.rollback()
        raise


def record_dispatch(db, episode, joined_sha256, acceptance, xml_sha256):
    """Only the guarded CLI calls this after its exact XML approval and send."""
    with db:
        db.execute('BEGIN IMMEDIATE')
        d = view(db, episode)
        if d['state'] != 'review_required' or not d['approvalRequests']:
            raise ValueError('Episode escalation approval request required')
        if joined_sha256 not in [o['joinedSha256'] for o in d['observations']]:
            raise ValueError('Dispatch evidence is not associated with episode')
        if acceptance.get('state') != 'accepted':
            raise ValueError('Native transport acceptance missing')
        db.execute('INSERT OR REPLACE INTO native_dispatches VALUES (?,?)',(episode,json.dumps(dict(acceptance=acceptance,xml_sha256=xml_sha256,joined_sha256=joined_sha256))))
        db.execute("UPDATE episodes SET state='escalated' WHERE id=?",(episode,))


def reserve_dispatch(db, episode, joined_sha256, xml_sha256, expected_revision=None):
    """Freeze operator decisions before the CLI network send; unknown outcomes stay reserved."""
    with db:
        db.execute('BEGIN IMMEDIATE')
        d = view(db,episode)
        if d['state'] != 'review_required' or not d['approvalRequests'] or joined_sha256 not in [o['joinedSha256'] for o in d['observations']]:
            raise ValueError('Matching episode escalation request required')
        ids = sorted(o['observationId'] for o in d['observations'])
        if expected_revision is not None and expected_revision != digest([ids,d['hafnia']]):
            raise ValueError('Evidence changed since human confirmation')
        if not any(r.get('revision') == digest([ids,d['hafnia']]) and r['evidence'] == ids for r in d['approvalRequests']):
            raise ValueError('Evidence changed since escalation request; request a new review')
        db.execute('INSERT INTO native_dispatches VALUES (?,?)',(episode,json.dumps(dict(state='reserved',joined_sha256=joined_sha256,xml_sha256=xml_sha256))))
