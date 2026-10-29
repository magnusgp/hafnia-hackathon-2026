"""Native handoff to the XProtect Event Server, separate from the local review decision.

Reuses the existing serializer, claim-before-POST ledger and one-attempt send. The transport (HTTP connection class) is
injectable so automated tests can never reach the real Event Server. Transport acceptance and Smart Client verification
are different states and are reported separately.
"""
import hashlib
import http.client
import json
from pathlib import Path

from scene_contracts.analytics_event import AnalyticsEventError, Ledger, build, dispatch_key, send

CONTRACT = 'ortru-review'


class Native:
    def __init__(self, ledger_path, target, enabled, status_path, destinations=None, connection=http.client.HTTPConnection, historical=None):
        self.ledger_path, self.target, self.enabled = Path(ledger_path), target, enabled
        self.status_path = Path(status_path)
        self.destinations, self.connection = destinations or {}, connection
        self.historical = historical or {}  # read-only: status of alarms sent before Ortru existed

    def payload(self, view):
        h, trig = view['handoff'], view['vision']['trigger']
        key = dispatch_key(view['hafnia']['summaryId'], CONTRACT, h['event'])
        left, top, right, bottom = trig['box']
        xml = build(h['event'], view['camera']['id'], trig['timestamp'], key, description=h['message'], start=view['interval'][0],
                    end=view['interval'][1], boxes=[dict(top=top, left=left, bottom=bottom, right=right)], vendor='Ortru')
        return key, xml

    def _status(self):
        return json.loads(self.status_path.read_text(encoding='utf-8')) if self.status_path.exists() else {}

    def attempts(self, key):
        ledger = Ledger(self.ledger_path)
        try:
            return ledger.attempts(key)
        finally:
            ledger.close()

    def state(self, view):
        """What the operator sees about the native path. Three independent facts: destination, transport, Smart Client."""
        h = view.get('handoff')
        if not h:
            return dict(state='no_event', destination=None, detail='This assessment has nothing to hand off.')
        if not h['alarm']:
            return dict(state='not_configured', destination=None,
                        detail='No XProtect alarm is set up for this camera. Review is available; sending is not.')
        out = dict(state='ready', destination=dict(event=h['event'], alarm=h['alarm'], target=self.target, camera=h['camera']),
                   detail='Review the event, then confirm to send.', transport=None, smartClient='not_verified')
        key, _ = self.payload(view)
        prior = self.attempts(key)
        mine = self._status().get(view['id'], {})
        if prior:
            last = prior[-1]
            accepted = last['state'] in ('accepted', 'reconciled_sent')
            out.update(state='sent' if accepted else 'uncertain' if last['state'] in ('claimed', 'uncertain') else 'blocked',
                       transport=dict(state=last['state'], attempt=last['attempt'], at=last['updated_at'], httpStatus=last['http_status']),
                       detail='The Event Server accepted the event. Confirming the alarm in Smart Client is a separate step.' if accepted
                       else 'The result of the send is not certain. It will not be sent again; check the Event Server and Smart Client.'
                       if last['state'] in ('claimed', 'uncertain') else f"The Event Server did not accept it ({last['state']}). {last['response'] or ''}".strip())
            out['smartClient'] = mine.get('smartClient', 'not_verified')
        return out

    def preview(self, view):
        key, xml = self.payload(view)
        return dict(dispatchKey=key, sha256=hashlib.sha256(xml).hexdigest(), xml=xml.decode(), destination=self.target, camera=view['handoff']['camera'],
                    event=view['handoff']['event'], alarm=view['handoff']['alarm'], enabled=self.enabled,
                    previous=[dict(attempt=a['attempt'], state=a['state'], at=a['created_at']) for a in self.attempts(key)],
                    consequence='Creates a native XProtect alarm on this camera. Event Server acceptance does not prove the alarm appears in Smart Client.')

    def send(self, view, approval):
        if not self.enabled:
            raise ValueError('Sending to XProtect is switched off in this session.')
        if not view.get('handoff') or not view['handoff']['alarm']:
            raise ValueError('No XProtect alarm is set up for this camera.')
        key, xml = self.payload(view)
        ledger = Ledger(self.ledger_path)
        try:
            row = send(ledger, key, xml, self.target, approval, connection=self.connection)
        except AnalyticsEventError as exc:
            raise ValueError(str(exc))
        finally:
            ledger.close()
        status = self._status()
        status.setdefault(view['id'], {}).update(dispatchKey=key, payloadSha256=row['payload_sha256'], httpStatus=row['http_status'],
                                                 transportState=row['state'], smartClient='not_verified')
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(json.dumps(status, indent=2), encoding='utf-8')
        return row


def refuse(exc):
    return isinstance(exc, (ValueError, AnalyticsEventError))
