"""SQLite observation ledger and camera/contract review cases (not incident counts)."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import UUID

from .contracts import assess
from .gateway import format_utc


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamps must include a UTC offset')
    if dt.microsecond:
        raise ValueError('Recorded intervals currently require whole-second timestamps')
    return format_utc(dt)


def interval(start, end):
    start, end = utc(start), utc(end)
    if start >= end:
        raise ValueError('Start must precede end')
    return start, end


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS operator_contracts (
                id TEXT PRIMARY KEY, contract_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, metadata TEXT NOT NULL,
                summary_id TEXT, message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY, camera_id TEXT NOT NULL, contract_id TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('observed','review_required','reviewed')),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(camera_id,contract_id));
            CREATE TABLE IF NOT EXISTS observations (
                summary_id TEXT PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
                camera_id TEXT NOT NULL, camera_name TEXT NOT NULL, clip_start TEXT NOT NULL, clip_end TEXT NOT NULL,
                contract_id TEXT NOT NULL, contract_version TEXT NOT NULL, contract_json TEXT NOT NULL,
                raw_ref TEXT NOT NULL, raw_response TEXT NOT NULL, assessment TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK(outcome IN ('positive','negative','uncertain')), created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
                kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alarm_checks (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
                status TEXT NOT NULL, alarm_id TEXT, detail TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def ingest(self, contract, item, camera_id, camera_name, start, end):
        camera_id = str(UUID(camera_id))
        start, end = interval(start, end)
        if camera_name not in contract['camera_names']:
            raise ValueError('Camera name is not selected by this contract')
        sid = item.get('Id')
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError('Gateway result requires a summary Id')
        if item.get('Progress') not in {'Completed', 'Failed'}:
            raise ValueError('Result is still pending; ingest a terminal result later')
        result = assess(contract, item)
        snapshot = json.dumps(contract, sort_keys=True)
        raw_fields = ('Id', 'Progress', 'Response', 'LastError') if 'LastError' in item else ('Id', 'Progress', 'Response')
        raw = json.dumps({k: item.get(k) for k in raw_fields}, sort_keys=True)
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            existing = self.db.execute('SELECT * FROM observations WHERE summary_id=?', (sid,)).fetchone()
            if existing:
                expected = (camera_id, camera_name, start, end, snapshot, raw)
                actual = tuple(existing[k] for k in ('camera_id', 'camera_name', 'clip_start', 'clip_end', 'contract_json', 'raw_response'))
                if actual != expected:
                    raise ValueError('Summary ID already ingested with different provenance or content')
                return dict(existing), False
            state = 'observed' if result['outcome'] == 'negative' else 'review_required'
            self.db.execute('''INSERT INTO cases(camera_id,contract_id,state,created_at,updated_at) VALUES (?,?,?,?,?)
                ON CONFLICT(camera_id,contract_id) DO UPDATE SET updated_at=excluded.updated_at,
                state=CASE WHEN excluded.state='review_required' THEN 'review_required' ELSE cases.state END''',
                (camera_id, contract['id'], state, now, now))
            case = self.db.execute('SELECT id FROM cases WHERE camera_id=? AND contract_id=?', (camera_id, contract['id'])).fetchone()[0]
            self.db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (sid, case, camera_id, camera_name, start, end, contract['id'], contract['version'], snapshot,
                 f'sqlite:observations/{sid}/raw_response', raw, json.dumps(result), result['outcome'], now))
            self.db.execute('INSERT INTO history(case_id,kind,detail,created_at) VALUES (?,?,?,?)',
                            (case, 'observation', sid, now))
        return dict(self.db.execute('SELECT * FROM observations WHERE summary_id=?', (sid,)).fetchone()), True

    def cases(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM cases ORDER BY id')]

    def case(self, case_id):
        row = self.db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown case ID')
        result = dict(row)
        for table in ('observations', 'history', 'alarm_checks'):
            result[table] = [dict(r) for r in self.db.execute(f'SELECT * FROM {table} WHERE case_id=?', (case_id,))]
        for observation in result['observations']:
            for field in ('contract_json', 'raw_response', 'assessment'):
                observation[field] = json.loads(observation[field])
        for check in result['alarm_checks']:
            check['detail'] = json.loads(check['detail'])
        return result

    def review(self, case_id, note):
        self.case(case_id)
        if not note.strip():
            raise ValueError('An operator review note is required')
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute("UPDATE cases SET state='reviewed',updated_at=? WHERE id=?", (now, case_id))
            self.db.execute('INSERT INTO history(case_id,kind,detail,created_at) VALUES (?,?,?,?)',
                            (case_id, 'operator_review', note, now))

    def record_alarm_check(self, case_id, status, alarm_id, detail):
        self.case(case_id)
        with self.db:
            self.db.execute('INSERT INTO alarm_checks(case_id,status,alarm_id,detail,created_at) VALUES (?,?,?,?,?)',
                            (case_id, status, alarm_id, json.dumps(detail), datetime.now(timezone.utc).isoformat()))
