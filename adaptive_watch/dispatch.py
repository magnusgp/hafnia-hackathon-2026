"""Shared source validation and durable native dispatch. Never retries uncertain sends."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from adaptive_watch.incident import assemble, proposal, sha, spatial_config
from adaptive_watch.capabilities import camera_config
from scene_contracts.analytics_event import Ledger, NS, send


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def validate_dispatch(a, root):
    e = json.loads((root/'joined.json').read_text())
    capability = camera_config(e['camera_name'], e['camera_guid'])
    camera = capability['camera_guid']
    if getattr(a, 'camera', capability['name']) != capability['name']:
        raise ValueError('Selected camera differs from evidence')
    meta = json.loads((root/'proposal.json').read_text())
    payload = (root/'proposal.xml').read_bytes()
    if not meta['dispatch_review_ready'] or not e.get('dispatch_review_ready'):
        raise ValueError('Fresh evidence gates not met; retrospective repair cannot authorize dispatch')
    if sha(root/'joined.json') != meta['evidence_sha256'] or hashlib.sha256(payload).hexdigest()!=meta['xml_sha256']:
        raise ValueError('Evidence or XML changed; rebuild and review')
    if sha(a.spatial) != e['spatial_sha256'] or spatial_config(a.spatial,camera).get('approved') is not True:
        raise ValueError('Approved camera-specific polygon changed or missing')
    saved_config = e.get('capability_config')
    if saved_config != capability:
        raise ValueError('Camera capability changed after analysis; review a new proposal')
    cv_path = root/(capability['name']+'.json')
    manifests = list((root/'acquisition').glob('*/manifest.json'))
    records = list((root/'hafnia').glob('*.json'))
    if len(manifests) != 1 or len(records) != 1:
        raise ValueError('Expected exact persisted source artifacts')
    geometry = e.get('geometry_registration')
    if geometry and sha(geometry['path']) != geometry['sha256']:
        raise ValueError('Camera calibration report changed')
    rebuilt = assemble(cv_path, manifests[0], records[0], a.spatial, geometry['path'] if geometry else None)
    expected, _ = proposal(rebuilt, meta['event_created_utc'])
    if expected != payload or not rebuilt['dispatch_review_ready']:
        raise ValueError('Exact proposal differs from validated sources')
    return e, meta, payload, capability


def execute_dispatch(a, root, approval, sender=None):
    e, meta, payload, capability = validate_dispatch(a, root)
    camera = capability['camera_guid']
    if approval != meta["xml_sha256"]:
        raise ValueError("Exact evidence approval changed")
    if not a.ledger or not Path(a.ledger).is_file():
        raise ValueError("Existing persistent dispatch ledger required")
    a.episode_root = getattr(a,'episode_root',None)
    a.episode_id = getattr(a,'episode_id',None)
    if bool(a.episode_root) != bool(a.episode_id):
        raise ValueError('Provide both episode root and ID')
    if a.episode_root:
        from adaptive_watch.evidence_api import EvidenceStore
        store = EvidenceStore(a.episode_root)
        try:
            episode = store.get(a.episode_id)
            if episode['state'] != 'review_required' or not episode['approvalRequests'] or sha(root/'joined.json') not in [o['joinedSha256'] for o in episode['observations']]:
                raise ValueError('Matching episode escalation request required')
        finally:
            store.close()
    ledger = Ledger(a.ledger)
    try:
        # Transactional reservation rejects overlapping windows across prompt variants
        # and different roots. A crash leaves a reservation for manual reconciliation.
        ledger.db.execute('CREATE TABLE IF NOT EXISTS sidewalk_episodes (key TEXT PRIMARY KEY,camera TEXT,start REAL,end REAL)')
        start,end = [datetime.fromisoformat(v.replace('Z','+00:00')).timestamp() for v in e['interval_utc']]
        with ledger.db:
            ledger.db.execute('BEGIN IMMEDIATE')
            overlaps = ledger.db.execute('SELECT key FROM sidewalk_episodes WHERE camera=? AND start<? AND end>?',
                                         (camera,end,start)).fetchall()
            if overlaps:
                raise ValueError('Episode already reserved; reconcile existing outcome, no automatic retry')
            # Include prior events from the existing persistent dispatch ledger.
            for row in ledger.db.execute('SELECT payload FROM analytics_dispatches'):
                xml = ET.fromstring(row[0]); ns = {'m':NS}
                prior_camera = xml.findtext('.//m:Source/m:FQID/m:ObjectId',namespaces=ns)
                first = xml.findtext('m:StartTime',namespaces=ns)
                last = xml.findtext('m:EndTime',namespaces=ns)
                if prior_camera and prior_camera.lower()==capability['camera_guid'] and first and last:
                    fs,ls = [datetime.fromisoformat(v.replace('Z','+00:00')).timestamp() for v in (first,last)]
                    if fs<end and ls>start:
                        raise ValueError('Overlapping dispatch already exists; review persistent ledger')
            ledger.db.execute('INSERT INTO sidewalk_episodes VALUES (?,?,?,?)',(meta['dispatch_key'],capability['camera_guid'],start,end))
        if a.episode_root:
            from adaptive_watch.episodes import reserve_dispatch
            store = EvidenceStore(a.episode_root)
            try:
                reserve_dispatch(store.db,a.episode_id,sha(root/'joined.json'),approval,getattr(a,'confirmed_revision',None))
            finally:
                store.close()
        result = (sender or send)(ledger,meta['dispatch_key'],payload,a.target,approval)
        write(root/'acceptance.json',result)
        print('Event Server result:',result['state'],'; verify native alarm separately.')
        if result['state']=='accepted' and a.episode_root:
            from adaptive_watch.episodes import record_dispatch
            store = EvidenceStore(a.episode_root)
            try:
                record_dispatch(store.db,a.episode_id,sha(root/'joined.json'),result,approval)
            finally:
                store.close()
        if result['state'] != 'accepted' and a.episode_root:
            store = EvidenceStore(a.episode_root)
            try:
                with store.db:
                    store.db.execute('UPDATE native_dispatches SET document=? WHERE episode=?',
                        (json.dumps(dict(acceptance=result,xml_sha256=approval,joined_sha256=sha(root/'joined.json'))),a.episode_id))
            finally:
                store.close()
        return result
    finally:
        ledger.close()
