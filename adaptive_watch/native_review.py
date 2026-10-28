"""Guarded native handoff of one review exception to the XProtect Event Server.

Preview builds the exact XML and its SHA-256. Send needs that digest back and an explicit confirmation,
goes through the existing claim-before-POST ledger, and never retries. A 200 from the Event Server is
transport acceptance only; the alarm must be verified separately in Smart Client.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from scene_contracts.analytics_event import Ledger, build, dispatch_key, send

EVENT_NAME = 'Adaptive Watch Review Required'


class NativeReview:
    def __init__(self, release, target, enabled=False):
        self.release, self.target, self.enabled = Path(release), target, enabled
        self.release.mkdir(parents=True, exist_ok=True)
        self.status_path = self.release/'native/status.json'

    def payload(self, case, camera_guid, include_box=False):
        """One deterministic AnalyticsEvent for the case's trigger moment (source camera, source time)."""
        trigger = case['vision']['trigger']
        key = dispatch_key(case['hafnia']['summaryId'], 'adaptive-watch-review', EVENT_NAME)
        boxes = []
        if include_box and trigger.get('box'):
            left, top, right, bottom = trigger['box']
            boxes = [dict(top=top, left=left, bottom=bottom, right=right)]
        xml = build(EVENT_NAME, camera_guid, trigger['timestamp'], key, description=case['handoff']['message'],
                    start=case['interval'][0], end=case['interval'][1], boxes=boxes, vendor='Adaptive Watch')
        return key, xml

    def preview(self, case, camera_guid, include_box=False):
        key, xml = self.payload(case, camera_guid, include_box)
        ledger = Ledger(self.release/'native/ledger.sqlite3')
        try:
            attempts = ledger.attempts(key)
        finally:
            ledger.close()
        return dict(dispatchKey=key, sha256=hashlib.sha256(xml).hexdigest(), xml=xml.decode(), destination=self.target,
                    camera=case['handoff']['camera'], event=EVENT_NAME, enabled=self.enabled,
                    previous=[dict(attempt=a['attempt'], state=a['state'], at=a['created_at']) for a in attempts],
                    consequence='Creates a native XProtect alarm on this camera. Event Server acceptance is not proof the alarm appears in Smart Client.')

    def send(self, case, case_id, camera_guid, approval, include_box=False):
        if not self.enabled:
            raise ValueError('Native sending is disabled in this session. Restart with native sending enabled to send.')
        key, xml = self.payload(case, camera_guid, include_box)
        ledger = Ledger(self.release/'native/ledger.sqlite3')
        try:
            row = send(ledger, key, xml, self.target, approval)
        finally:
            ledger.close()
        status = json.loads(self.status_path.read_text(encoding='utf-8')) if self.status_path.exists() else {}
        mine = status.get(case_id, {})
        state = {'accepted': 'sent', 'rejected_warning': 'blocked', 'rejected_http': 'blocked'}.get(row['state'], 'blocked')
        mine.update(state=state, sentAt=datetime.now(timezone.utc).isoformat(), dispatchKey=key, payloadSha256=row['payload_sha256'],
                    httpStatus=row['http_status'], response=row['response'],
                    detail='The Event Server accepted it. Confirm the alarm in Smart Client.' if state == 'sent'
                    else f"The Event Server did not accept it ({row['state']}). {row['response'] or row['note'] or ''}".strip())
        status[case_id] = mine
        self.status_path.write_text(json.dumps(status, indent=2), encoding='utf-8')
        return row
