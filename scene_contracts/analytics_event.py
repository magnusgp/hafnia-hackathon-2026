"""Native XProtect analytics events over the documented XML protocol (no REST/OAuth).

Protocol: https://doc.developer.milestonesys.com/mipsdk/reference/protocols/analytics_and_mad_events.html
Schema:   https://doc.developer.milestonesys.com/XSD/AnalyticsEvent.xsd (copy in tests/fixtures/)

The Event Server listens on its Analytics Receive port (default 9090), plain HTTP, no
authentication beyond its allowed-address list. EventHeader/Message must equal the
Analytics Event name configured in Management Client. HTTP 200 with a "Warning:" body
means the event was NOT matched to a device or definition; only an empty 200 is accepted.

Sending is never automatic: a preview prints the exact bytes and their SHA-256, and a
send requires that digest back as approval. Every attempt is claimed in SQLite before
the POST; an uncertain outcome blocks further attempts until an operator reconciles it.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import re
import sqlite3
from uuid import UUID
import xml.etree.ElementTree as ET

NS = 'urn:milestone-systems'
CAMERA_KIND = '5135ba21-f1dc-4321-806a-6ce2017343c0'
ZERO_GUID = '00000000-0000-0000-0000-000000000000'  # documented: server assigns the event ID
DEFAULT_EVENT_MAP = Path(__file__).resolve().parent.parent / 'config' / 'analytics-events.json'
DESCRIPTION_LIMIT = 1000
GUID = re.compile(r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}')

# xs:sequence order from AnalyticsEvent.xsd; only the subset this serializer emits is validated.
ORDER = {
    'AnalyticsEvent': ['EventHeader', 'Description', 'StartTime', 'EndTime', 'Location', 'Count', 'RuleList',
                       'ObjectList', 'ReferenceList', 'SnapshotList', 'Vendor'],
    'EventHeader': ['ID', 'Timestamp', 'Class', 'Type', 'Version', 'Priority', 'Name', 'Message', 'CustomTag', 'Source'],
    'Source': ['Name', 'Description', 'FQID'],
    'FQID': ['ServerId', 'ParentId', 'ObjectId', 'ObjectIdString', 'FolderType', 'Kind'],
    'ServerId': ['Type', 'Hostname', 'Port', 'Id'],
    'Object': ['ID', 'Name', 'Type', 'Description', 'Confidence', 'Value', 'AlarmTrigger', 'Removed', 'Color',
               'Size', 'SizeUnit', 'BoundingBox', 'Polygon', 'Motion', 'Mask'],
    'BoundingBox': ['Top', 'Left', 'Bottom', 'Right', 'Color'],
    'Vendor': ['Name', 'CustomData'],
}
REQUIRED = {'AnalyticsEvent': {'EventHeader'}, 'EventHeader': {'ID', 'Timestamp', 'Message'},
            'ServerId': {'Id'}, 'BoundingBox': {'Top', 'Left', 'Bottom', 'Right'}}


class AnalyticsEventError(Exception):
    pass


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Event times must include a UTC offset')
    return value.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _guid(value):
    return str(UUID(str(value)))


def resolve_message(event_map, contract_id, outcome):
    """Exact (contract, outcome) -> configured Analytics Event name; anything else is refused."""
    rows = [r for r in event_map['events'] if r['contract'] == contract_id and r['outcome'] == outcome]
    if len(rows) != 1:
        raise AnalyticsEventError(f'No unique analytics event mapped for {contract_id}/{outcome}; nothing to send')
    return rows[0]['message']


def load_event_map(path=DEFAULT_EVENT_MAP):
    m = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    keys = [(r['contract'], r['outcome']) for r in m.get('events', [])]
    if not keys or len(keys) != len(set(keys)):
        raise ValueError('Event map needs unique contract/outcome rows')
    for r in m['events']:
        if r['outcome'] not in {'positive', 'negative', 'uncertain'} or not r.get('message', '').strip():
            raise ValueError('Event map row needs an outcome and a non-empty message')
        if r['message'] != r['message'].strip():
            raise ValueError('Event message must not have surrounding whitespace (exact match)')
    return m


def build(message, camera_id, timestamp, dispatch_key, description=None, start=None, end=None,
          server_id=None, boxes=(), vendor='Hafnia Scene Contracts'):
    """Serialize one AnalyticsEvent. Deterministic for identical inputs (byte-for-byte)."""
    def sub(parent, tag, text=None):
        el = ET.SubElement(parent, f'{{{NS}}}{tag}')
        if text is not None:
            el.text = str(text)
        return el

    if not message or message != message.strip():
        raise ValueError('Message must equal the configured Analytics Event name exactly')
    root = ET.Element(f'{{{NS}}}AnalyticsEvent')
    header = sub(root, 'EventHeader')
    sub(header, 'ID', ZERO_GUID)
    sub(header, 'Timestamp', _utc(timestamp))
    sub(header, 'Type', 'Scene Contracts evidence')
    sub(header, 'Message', message)
    sub(header, 'CustomTag', dispatch_key)
    fqid = sub(sub(header, 'Source'), 'FQID')
    if server_id:
        # Documented FQID: ServerId{Type,Hostname,Port,Id}. A bare GUID emits Id only; a dict emits the full block.
        info = server_id if isinstance(server_id, dict) else dict(id=server_id)
        sid = sub(fqid, 'ServerId')
        for key, tag in (('type', 'Type'), ('hostname', 'Hostname'), ('port', 'Port')):
            if info.get(key) not in (None, ''):
                sub(sid, tag, info[key])
        sub(sid, 'Id', _guid(info['id']))
    sub(fqid, 'ObjectId', _guid(camera_id))
    sub(fqid, 'Kind', CAMERA_KIND)
    if description:
        sub(root, 'Description', description[:DESCRIPTION_LIMIT])
    if start:
        sub(root, 'StartTime', _utc(start))
    if end:
        sub(root, 'EndTime', _utc(end))
    if boxes:
        objects = sub(root, 'ObjectList')
        for box in boxes:
            bb = sub(sub(objects, 'Object'), 'BoundingBox')
            for k in ('top', 'left', 'bottom', 'right'):
                sub(bb, k.capitalize(), repr(float(box[k])))
    sub(sub(root, 'Vendor'), 'Name', vendor)
    ET.register_namespace('', NS)
    body = ET.tostring(root, encoding='unicode', short_empty_elements=True)
    data = ('<?xml version="1.0" encoding="utf-8"?>\n' + body).encode('utf-8')
    validate(data)
    return data


def validate(data):
    """Offline structural check against the XSD rules this serializer relies on."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise AnalyticsEventError(f'XML is not well formed: {exc}') from None
    if root.tag != f'{{{NS}}}AnalyticsEvent':
        raise AnalyticsEventError('Root must be AnalyticsEvent in namespace urn:milestone-systems')

    def local(el):
        if not el.tag.startswith(f'{{{NS}}}'):
            raise AnalyticsEventError(f'Element outside urn:milestone-systems: {el.tag}')
        return el.tag[len(NS) + 2:]

    def walk(el):
        name = local(el)
        children = [local(c) for c in el]
        if name in ORDER:
            order = ORDER[name]
            unknown = [c for c in children if c not in order]
            if unknown:
                raise AnalyticsEventError(f'{name}: unsupported child {unknown[0]}')
            idx = [order.index(c) for c in children]
            if idx != sorted(idx) or len(set(children)) != len(children):
                raise AnalyticsEventError(f'{name}: children out of schema order or repeated: {children}')
        missing = REQUIRED.get(name, set()) - set(children)
        if missing:
            raise AnalyticsEventError(f'{name}: missing required {sorted(missing)}')
        for c in el:
            walk(c)

    if local(root) != 'AnalyticsEvent':
        raise AnalyticsEventError('Unexpected root')
    walk(root)
    find = lambda path: root.findall(path, {'m': NS})
    for el in find('.//m:ID') + find('.//m:ObjectId') + find('.//m:Kind') + find('.//m:ServerId/m:Id'):
        if not GUID.fullmatch(el.text or ''):
            raise AnalyticsEventError(f'Invalid GUID in {local(el)}')
    for el in find('m:EventHeader/m:Timestamp') + find('m:StartTime') + find('m:EndTime'):
        try:
            _utc(el.text or '')
        except ValueError:
            raise AnalyticsEventError(f'Invalid xs:dateTime with offset in {local(el)}') from None
    if not (find('m:EventHeader/m:Message')[0].text or '').strip():
        raise AnalyticsEventError('Message is empty')
    for bb in find('.//m:BoundingBox'):
        t, l, b, r = (float(bb.find(f'm:{k}', {'m': NS}).text) for k in ('Top', 'Left', 'Bottom', 'Right'))
        if not (0 <= t <= b <= 1 and 0 <= l <= r <= 1):
            raise AnalyticsEventError('BoundingBox must be normalized [0,1] with top<=bottom, left<=right')
    return True


def dispatch_key(summary_id, contract_id, message):
    return 'sc1-' + hashlib.sha256(f'{summary_id}\n{contract_id}\n{message}'.encode()).hexdigest()[:32]


def classify(status, body):
    """Map the Event Server reply to a dispatch state. Only an empty 200 is 'accepted'."""
    text = (body or '').strip()
    if status == 200 and not text:
        return 'accepted'
    if status == 200:
        return 'rejected_warning'  # e.g. "Warning: Device not known" / "Warning: Event message not known"
    if status in (400, 403):
        return 'rejected_http'
    return 'uncertain'  # 5xx or anything undocumented: the server may or may not have processed it


class Ledger:
    """Persistent duplicate-dispatch protection. One row per attempt, claimed before the POST."""

    STATES = ('claimed', 'accepted', 'rejected_warning', 'rejected_http', 'uncertain', 'reconciled_sent',
              'reconciled_not_sent')
    # Attempts in these states may be followed by a new, explicitly requested attempt.
    RETRYABLE = {'rejected_warning', 'rejected_http', 'reconciled_not_sent'}

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        states = ','.join(f"'{s}'" for s in self.STATES)
        self.db.executescript(f'''
            CREATE TABLE IF NOT EXISTS analytics_dispatches (
                dispatch_key TEXT NOT NULL, attempt INTEGER NOT NULL, payload_sha256 TEXT NOT NULL,
                payload TEXT NOT NULL, target TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ({states})),
                http_status INTEGER, response TEXT, note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(dispatch_key, attempt));
        ''')

    def close(self):
        self.db.close()

    def attempts(self, key):
        return [dict(r) for r in self.db.execute(
            'SELECT * FROM analytics_dispatches WHERE dispatch_key=? ORDER BY attempt', (key,))]

    def claim(self, key, payload, target, reattempt=False):
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            last = self.db.execute('SELECT * FROM analytics_dispatches WHERE dispatch_key=? ORDER BY attempt DESC LIMIT 1',
                                   (key,)).fetchone()
            if last:
                if last['state'] not in self.RETRYABLE:
                    raise AnalyticsEventError(
                        f"Dispatch {key} already exists in state '{last['state']}'; not sending again. "
                        'An uncertain or claimed attempt must be reconciled by an operator first.')
                if not reattempt:
                    raise AnalyticsEventError(f"Dispatch {key} was {last['state']}; pass --reattempt to try once more")
            attempt = (last['attempt'] + 1) if last else 1
            self.db.execute('INSERT INTO analytics_dispatches VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            (key, attempt, hashlib.sha256(payload).hexdigest(), payload.decode('utf-8'), target,
                             'claimed', None, None, None, now, now))
        return attempt

    def finish(self, key, attempt, state, status=None, response=None, note=None):
        if state not in self.STATES:
            raise ValueError(state)
        with self.db:
            self.db.execute('UPDATE analytics_dispatches SET state=?, http_status=?, response=?, note=?, updated_at=? '
                            'WHERE dispatch_key=? AND attempt=?',
                            (state, status, response, note, datetime.now(timezone.utc).isoformat(), key, attempt))

    def reconcile(self, key, sent, note):
        if not note or not note.strip():
            raise ValueError('Reconciliation needs an operator note (what was checked in Smart Client/Event Server)')
        rows = self.attempts(key)
        if not rows or rows[-1]['state'] not in {'claimed', 'uncertain'}:
            raise AnalyticsEventError('Only a claimed or uncertain attempt can be reconciled')
        self.finish(key, rows[-1]['attempt'], 'reconciled_sent' if sent else 'reconciled_not_sent',
                    rows[-1]['http_status'], rows[-1]['response'], note)


def parse_target(target):
    host, sep, port = target.rpartition(':')
    if not sep or not host or not port.isdigit():
        raise ValueError('Target must be host:port, e.g. 127.0.0.1:9090')
    return host.strip('[]'), int(port)


def send(ledger, key, payload, target, approval, reattempt=False, timeout=10.0, connection=http.client.HTTPConnection):
    """POST once. Never retries. Returns the final ledger row."""
    validate(payload)
    digest = hashlib.sha256(payload).hexdigest()
    if not approval or len(approval) < 12 or not digest.startswith(approval.lower()):
        raise AnalyticsEventError('Approval must be the first 12+ hex digits of the previewed payload SHA-256')
    host, port = parse_target(target)
    attempt = ledger.claim(key, payload, target, reattempt)
    status = body = None
    try:
        conn = connection(host, port, timeout=timeout)
        try:
            conn.request('POST', '/', body=payload,
                         headers={'Content-Type': 'text/xml', 'Content-Length': str(len(payload))})
            resp = conn.getresponse()
            status, body = resp.status, resp.read(4096).decode('utf-8', 'replace')
        finally:
            conn.close()
    except ConnectionRefusedError as exc:
        # Nothing was accepted by a listener; still recorded, still manual.
        ledger.finish(key, attempt, 'rejected_http', None, None, f'connection refused: {exc}')
        return ledger.attempts(key)[-1]
    except (OSError, http.client.HTTPException) as exc:
        ledger.finish(key, attempt, 'uncertain', status, body, f'{type(exc).__name__}: {exc}')
        return ledger.attempts(key)[-1]
    ledger.finish(key, attempt, classify(status, body), status, body)
    return ledger.attempts(key)[-1]
