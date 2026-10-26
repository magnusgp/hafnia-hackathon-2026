"""Backend-owned, explicit human confirmations over the shared guarded dispatcher."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
from types import SimpleNamespace

from adaptive_watch import episodes
from adaptive_watch.dispatch import validate_dispatch, execute_dispatch
from adaptive_watch.incident import sha


class NativeActions:
    def __init__(self, config):
        self.config = Path(config).resolve()

    def context(self, store, identifier):
        config = json.loads(self.config.read_text(encoding='utf-8-sig'))
        d = store.get(identifier)
        if (config.get('configured') is not True or not config.get('configuration_verified_by') or
                not config.get('configuration_verified_at') or
                config.get('event_name') != 'Adaptive Watch Sidewalk Obstruction'):
            raise ValueError('Dedicated XProtect configuration has not been verified')
        if d['evidenceKind'] != 'fresh_analysis' or any(o.get('syntheticFixture') or o.get('loopReset') for o in d['observations']):
            raise ValueError('Native action requires fresh, coherent evidence')
        if d['state'] != 'review_required' or not d['approvalRequests']:
            raise ValueError('Review and request escalation first')
        if store.db.execute('SELECT 1 FROM native_dispatches WHERE episode=?', (identifier,)).fetchone():
            raise ValueError('Native action already reserved; administrator reconciliation required')
        entry = config['incidents'][d['cameraGuid']]
        root = Path(entry['root']).resolve()
        args = SimpleNamespace(camera=d['camera'], spatial=Path(entry['spatial']).resolve(),
                               ledger=Path(config['ledger']).resolve(), target=config['target'],
                               episode_root=store.root, episode_id=identifier)
        if not args.ledger.is_file():
            raise ValueError('Existing dispatch ledger unavailable')
        e, meta, payload, capability = validate_dispatch(args, root)
        if sha(root / 'joined.json') != d['joinedSha256']:
            raise ValueError('Configured source differs from reviewed incident')
        ids = sorted(o['observationId'] for o in d['observations'])
        revision = episodes.digest([ids, d['hafnia']])
        if not any(r.get('revision') == revision and r['evidence'] == ids for r in d['approvalRequests']):
            raise ValueError('Evidence changed; review and request escalation again')
        binding = dict(incident=identifier, revision=revision, config=sha(self.config),
                       payload=meta['xml_sha256'], evidence=sha(root / 'joined.json'),
                       destination=args.target, action='send_native_event')
        return d, args, root, binding, config

    def status(self, store, identifier):
        row = store.db.execute('SELECT document FROM native_dispatches WHERE episode=?', (identifier,)).fetchone()
        if row:
            record = json.loads(row[0])
            state = record.get('acceptance', {}).get('state', record.get('state', 'reserved'))
            return dict(available=False, state=state,
                        reason='Transport accepted; verify alarm, camera, playback and overlay in Smart Client separately.' if state == 'accepted'
                        else 'Dispatch reserved or uncertain. Administrator reconciliation required; do not retry.')
        try:
            d, args, root, binding, config = self.context(store, identifier)
            return dict(available=True, state='confirmation_required', destination=config['destination_label'])
        except (ValueError, KeyError, OSError, TypeError):
            return dict(available=False, state='unavailable', reason='Native prerequisites incomplete: review, approved geometry, fresh evidence and verified XProtect setup are required.')

    def prepare(self, store, identifier, session):
        d, args, root, binding, config = self.context(store, identifier)
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        store.db.execute('CREATE TABLE IF NOT EXISTS native_confirmations (token TEXT PRIMARY KEY, document TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)')
        with store.db:
            store.db.execute('INSERT INTO native_confirmations(token,document) VALUES (?,?)',
                             (episodes.digest(token), json.dumps(dict(binding=binding, session=session, expires=expiry))))
        return dict(token=token, expires=expiry, incident=identifier, title=d['title'], camera=d['camera'],
                    interval=d['interval'], destination=config['destination_label'],
                    action='Send one Adaptive Watch event to XProtect',
                    consequence='This may create a native alarm. Transport acceptance does not verify the alarm or its overlay.')

    def confirm(self, store, identifier, session, body):
        if body.get('confirmed') is not True:
            raise ValueError('Explicit human confirmation required')
        d, args, root, binding, config = self.context(store, identifier)
        store.db.execute('BEGIN IMMEDIATE')
        try:
            row = store.db.execute('SELECT document, consumed FROM native_confirmations WHERE token=?',
                                   (episodes.digest(body.get('token')),)).fetchone()
            if not row or row[1]:
                raise ValueError('Confirmation missing or already consumed')
            saved = json.loads(row[0])
            if (saved['session'] != session or saved['binding'] != binding or
                    datetime.fromisoformat(saved['expires']) < datetime.now(timezone.utc)):
                raise ValueError('Confirmation expired or evidence/destination changed')
            store.db.execute('UPDATE native_confirmations SET consumed=1 WHERE token=?', (episodes.digest(body['token']),))
            store.db.commit()
        except Exception:
            store.db.rollback()
            raise
        args.confirmed_revision = binding['revision']
        execute_dispatch(args, root, binding['payload'])
        return self.status(store, identifier)
