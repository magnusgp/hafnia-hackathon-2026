"""Watch configuration: validation, immutable versions, lifecycle. SQLite, one file, no secrets."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import threading
import uuid

from ortru import SCHEMA
from ortru.capabilities import check_detector
from ortru.policy import DEFAULT_RAISE, KINDS

STATUSES = ('draft', 'active', 'paused', 'disabled')
NATIVE_EVENT = 'Adaptive Watch Review Required'  # the event type that exists in XProtect today (docs/adaptive-watch/native-xprotect.md)
OUTPUT_KEYS = ['outcome', 'evidence', 'timing', 'limitations']
PROMPT_RULES = ('Do not use camera names as evidence. Return only a JSON object with exactly these keys: '
                '"outcome" ("supported", "not_observed", or "uncertain"), "evidence" (short visible facts), '
                '"timing" (approximate seconds relative to clip start, or unknown), "limitations" (what this clip cannot establish). '
                'Do not infer intent or facts outside the clip.')


class Conflict(ValueError):
    """The Watch changed since the editor loaded it."""


def now():
    return datetime.now(timezone.utc).isoformat()


def build_prompt(instruction):
    """The exact text sent to Hafnia: the operator's instruction plus the fixed answer contract the parser enforces."""
    return f'Assess whether the following is directly visible: {instruction.strip().rstrip(".")}. {PROMPT_RULES}'


def normalize(raw, catalog, destinations=None):
    """Validate an editor payload into the stored configuration. Raises ValueError with an operator-facing message."""
    if not isinstance(raw, dict):
        raise ValueError('Expected a Watch configuration')
    name = str(raw.get('name', '')).strip()
    if not 2 <= len(name) <= 60:
        raise ValueError('Give the Watch a name of 2 to 60 characters')
    guid = str(raw.get('cameraId', '')).strip().lower()
    cams = [c for c in catalog if c['id'].lower() == guid]
    if len(cams) != 1:
        raise ValueError('Choose a camera from the authorized XProtect camera catalog')
    h = raw.get('hafnia') or {}
    instruction, condition = str(h.get('instruction', '')).strip(), str(h.get('condition', '')).strip()
    if not 12 <= len(instruction) <= 500:
        raise ValueError('Write the Hafnia instruction as 12 to 500 characters describing what should be visible')
    if re.search(r'[\x00-\x08\x0b-\x1f`{}]|json|ignore (all|the|previous)', instruction, re.I):
        raise ValueError('The instruction must describe the visible event in plain words; Ortru adds the answer format')
    if not 3 <= len(condition) <= 60:
        raise ValueError('Name the visible condition in 3 to 60 characters, for example "Person on the track area"')
    detector, region = check_detector(raw.get('detector'), raw.get('region'))
    s = raw.get('schedule') or {}
    interval, window = s.get('intervalMinutes'), s.get('windowSeconds')
    if type(interval) is not int or not 5 <= interval <= 1440:
        raise ValueError('The cadence must be a whole number of minutes from 5 to 1440')
    if type(window) is not int or not 12 <= window <= 17:
        raise ValueError('The recording window must be 12 to 17 seconds (what Hafnia accepts)')
    q = raw.get('quota') or {}
    per_day = q.get('perDay')
    if type(per_day) is not int or not 1 <= per_day <= 100:
        raise ValueError('The daily Hafnia budget for this Watch must be 1 to 100 requests')
    p = raw.get('policy') or {}
    raise_on = p.get('raiseOn', list(DEFAULT_RAISE))
    if not isinstance(raise_on, list) or not raise_on or any(k not in KINDS for k in raise_on) or 'clear' in raise_on:
        raise ValueError('Choose which signal combinations raise an exception')
    alarm = (destinations or {}).get(cams[0]['id'].lower())  # only a verified, existing XProtect destination counts
    src = raw.get('source') or {}
    ref = src.get('loopReference')
    if ref is not None and (not isinstance(ref, str) or not re.fullmatch(r'runs/[A-Za-z0-9_./-]+manifest\.json', ref) or '..' in ref):
        raise ValueError('The loop reference must be a recorded manifest under runs/')
    return dict(
        schema=SCHEMA, name=name, camera=dict(id=cams[0]['id'], name=cams[0]['name']),
        hafnia=dict(instruction=instruction, condition=condition, prompt=build_prompt(instruction),
                    output=dict(keys=OUTPUT_KEYS, outcomes=['supported', 'not_observed', 'uncertain'])),
        detector=detector, region=region, **({'source': dict(loopReference=ref)} if ref else {}),
        policy=dict(raiseOn=sorted(set(raise_on), key=KINDS.index)),
        schedule=dict(intervalMinutes=interval, windowSeconds=window, marginSeconds=90),
        quota=dict(perDay=per_day),
        native=dict(event=NATIVE_EVENT, alarm=alarm))


class Watches:
    def __init__(self, db_path, catalog, destinations=None):
        self.path, self.catalog, self.destinations = Path(db_path), catalog, destinations or {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS watches(id TEXT PRIMARY KEY, status TEXT NOT NULL, version INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS watch_versions(watch_id TEXT NOT NULL, version INTEGER NOT NULL, config TEXT NOT NULL, created TEXT NOT NULL,
                PRIMARY KEY(watch_id, version));
            CREATE TABLE IF NOT EXISTS watch_events(id INTEGER PRIMARY KEY AUTOINCREMENT, watch_id TEXT NOT NULL, at TEXT NOT NULL, text TEXT NOT NULL);''')

    def db(self):
        outer = self

        class C:
            def __enter__(s):
                s.d = sqlite3.connect(outer.path, timeout=15, isolation_level=None)
                s.d.row_factory = sqlite3.Row
                return s.d

            def __exit__(s, *e):
                s.d.close()
        return C()

    def _view(self, db, row):
        cfg = json.loads(db.execute('SELECT config FROM watch_versions WHERE watch_id=? AND version=?', (row['id'], row['version'])).fetchone()[0])
        return dict(id=row['id'], status=row['status'], version=row['version'], updated=row['updated'], config=cfg,
                    problems=self.activation_problems(cfg))

    def activation_problems(self, cfg):
        """Why this Watch cannot do everything yet. `blocking` ones prevent activation."""
        out = []
        if not cfg['native']['alarm']:
            out.append(dict(code='native_not_configured', blocking=False,
                            text='No XProtect alarm is set up for this camera, so exceptions can be reviewed but not sent. '
                                 'Setting one up changes XProtect and needs your explicit approval.'))
        return out

    def list(self):
        with self.db() as db:
            return [self._view(db, r) for r in db.execute('SELECT * FROM watches ORDER BY created, id')]

    def get(self, watch_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM watches WHERE id=?', (watch_id,)).fetchone()
            if row is None:
                raise KeyError(watch_id)
            return self._view(db, row)

    def version_config(self, watch_id, version):
        with self.db() as db:
            row = db.execute('SELECT config FROM watch_versions WHERE watch_id=? AND version=?', (watch_id, version)).fetchone()
        if row is None:
            raise KeyError((watch_id, version))
        return json.loads(row[0])

    def versions(self, watch_id):
        with self.db() as db:
            return [dict(version=r['version'], created=r['created'], config=json.loads(r['config']))
                    for r in db.execute('SELECT * FROM watch_versions WHERE watch_id=? ORDER BY version', (watch_id,))]

    def history(self, watch_id):
        with self.db() as db:
            return [dict(at=r['at'], text=r['text']) for r in db.execute('SELECT at,text FROM watch_events WHERE watch_id=? ORDER BY id', (watch_id,))]

    def _log(self, db, watch_id, text):
        db.execute('INSERT INTO watch_events(watch_id,at,text) VALUES (?,?,?)', (watch_id, now(), text))

    def create(self, raw):
        cfg = normalize(raw, self.catalog, self.destinations)
        wid, t = 'w-'+uuid.uuid4().hex[:10], now()
        with self.lock, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO watches VALUES (?,?,?,?,?)', (wid, 'draft', 1, t, t))
            db.execute('INSERT INTO watch_versions VALUES (?,?,?,?)', (wid, 1, json.dumps(cfg), t))
            self._log(db, wid, 'Created as a draft (version 1)')
            db.execute('COMMIT')
        return self.get(wid)

    def edit(self, watch_id, base_version, raw):
        """Saves a new immutable version. Fails when the editor was opened on an older version."""
        cfg = normalize(raw, self.catalog, self.destinations)
        with self.lock, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM watches WHERE id=?', (watch_id,)).fetchone()
            if row is None:
                db.execute('ROLLBACK')
                raise KeyError(watch_id)
            if row['version'] != base_version:
                db.execute('ROLLBACK')
                raise Conflict(f"This Watch is now at version {row['version']}; you were editing version {base_version}. Reload to see the latest.")
            same = json.loads(db.execute('SELECT config FROM watch_versions WHERE watch_id=? AND version=?', (watch_id, base_version)).fetchone()[0]) == cfg
            if same:
                db.execute('ROLLBACK')
                return self.get(watch_id)
            v, t = base_version+1, now()
            db.execute('INSERT INTO watch_versions VALUES (?,?,?,?)', (watch_id, v, json.dumps(cfg), t))
            db.execute('UPDATE watches SET version=?, updated=? WHERE id=?', (v, t, watch_id))
            self._log(db, watch_id, f'Saved version {v}')
            db.execute('COMMIT')
        return self.get(watch_id)

    def set_status(self, watch_id, status, base_version=None):
        if status not in STATUSES[1:]:
            raise ValueError('Status must be active, paused or disabled')
        with self.lock, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM watches WHERE id=?', (watch_id,)).fetchone()
            if row is None:
                db.execute('ROLLBACK')
                raise KeyError(watch_id)
            if base_version is not None and row['version'] != base_version:
                db.execute('ROLLBACK')
                raise Conflict(f"This Watch is now at version {row['version']}. Reload to see the latest.")
            db.execute('UPDATE watches SET status=?, updated=? WHERE id=?', (status, now(), watch_id))
            self._log(db, watch_id, {'active': 'Activated', 'paused': 'Paused', 'disabled': 'Disabled'}[status])
            db.execute('COMMIT')
        return self.get(watch_id)
