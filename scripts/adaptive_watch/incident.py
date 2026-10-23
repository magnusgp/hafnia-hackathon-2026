"""Operator-invoked scooter workflow; acquisition, bounded analysis, review, approved send.

No unattended alarms. Run --help for stages. Private outputs only.
"""
import argparse
import getpass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adaptive_watch.incident import SCOOTER, assemble, proposal, sha, spatial_config
from adaptive_watch.evaluation import Evaluation
from scene_contracts.analytics_event import Ledger, NS, send
from scene_contracts.gateway import Gateway

REPO = Path(__file__).resolve().parents[2]
CAMERA = 'escooter_left_across_sidewalk'


def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    tmp.replace(path)


def run(args):
    subprocess.run([str(x) for x in args], check=True)


def terminal_login(gateway):
    """Use the existing login endpoint, accepting credentials only from the terminal."""
    if not sys.stdin.isatty():
        raise ValueError('User-opened interactive terminal required for gateway password entry')
    password = getpass.getpass('Gateway administrator password: ')
    response = gateway.request('POST','/api/Sessions/Login',
                               dict(Name='administrator',Password=password),login=True)
    gateway.session = response.get('Id') if isinstance(response,dict) else None
    if not gateway.session:
        raise ValueError('Gateway login returned no session ID')


def analyze(a, root):
    manifests = list((root/'acquisition').glob('*/manifest.json'))
    if len(manifests) != 1:
        raise ValueError('Need exactly one acquired recording')
    manifest = manifests[0]
    m = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if m['camera_id'].lower() != SCOOTER or m['camera_name'] != CAMERA:
        raise ValueError('Camera mapping mismatch')
    spatial = spatial_config(a.spatial, SCOOTER)
    if not (root/'continuity.json').exists():
        print('Review acquired snapshots/MKV in', manifest.parent)
        print('Confirm a coherent recording with placement and stationarity; no synthetic loop boundary.')
        if input('Type NO LOOP BOUNDARY after visually checking: ') != 'NO LOOP BOUNDARY':
            raise ValueError('Continuity review pending')
        write(root/'continuity.json', dict(manifest_sha256=sha(manifest), reviewed_at=datetime.now(timezone.utc).isoformat()))
    if json.loads((root/'continuity.json').read_text())['manifest_sha256'] != sha(manifest):
        raise ValueError('Recording changed after continuity review')
    # Commands sent through SSH contain only validated paths and fixed arguments.
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', a.ssh_user):
        raise ValueError('Specify existing Linux SSH user')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', a.linux_python):
        raise ValueError('Linux Python must be an absolute simple path')
    remote = '/tmp/adaptive-watch-'+hashlib.sha256(str(root).encode()).hexdigest()[:20]
    host = a.ssh_user+'@p022-linux'
    ssh = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
    scp = ['scp','-o','BatchMode=yes','-o','ConnectTimeout=10']
    if a.identity:
        ssh += ['-i',a.identity]; scp += ['-i',a.identity]
    # Gateway video URIs have second precision. Select a whole-second subset
    # rather than silently rounding a fractional acquisition boundary.
    bounds = [datetime.fromisoformat(m[k].replace('Z','+00:00')).timestamp()
              for k in ('requested_start_utc','requested_end_utc')]
    start,end = [datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                 for t in (math.ceil(bounds[0]), math.floor(bounds[1]))]
    scene = dict(name=CAMERA,manifest=remote+'/recording/manifest.json',
                 start=start,end=end,
                 queries=['an electric scooter','a scooter lying on the ground'],
                 walkway=spatial['polygon'],walkway_approved=spatial.get('approved') is True)
    cfg = dict(model_id='google/owlvit-base-patch32',
               model_revision='cbc355fb364588351c5d51c7f74465e8e7ec6f72',scenes=[scene])
    write(root/'cv-config.json',cfg)
    cv_path = root/(CAMERA+'.json')
    if not cv_path.exists():
        run(ssh+[host,'mkdir -p '+remote+'/recording'])
        files = [manifest]
        for f in m['frames']:
            path = (manifest.parent/f['file']).resolve()
            if not path.is_relative_to(manifest.parent.resolve()) or sha(path) != f['sha256']:
                raise ValueError('Acquired frame path or hash mismatch')
            files.append(path)
        run(scp+files+[host+':'+remote+'/recording/'])
        run(scp+[REPO/'scripts/adaptive_watch/sidewalk_cv.py',root/'cv-config.json',host+':'+remote+'/'])
        run(ssh+[host,a.linux_python+' '+remote+'/sidewalk_cv.py '+remote+'/cv-config.json --out '+remote+'/cv'])
        run(scp+[host+':'+remote+'/cv/'+CAMERA+'.json',cv_path])
    cv = json.loads(cv_path.read_text())
    if cv.get('runner_sha256') != sha(REPO/'scripts/adaptive_watch/sidewalk_cv.py') or cv.get('config_sha256') != sha(root/'cv-config.json'):
        raise ValueError('Saved CV runner/config differs; retain evidence and review before a new run')
    ev = Evaluation(root/'hafnia')
    try:
        entry = dict(scene=CAMERA,camera_id=SCOOTER,start=scene['start'],end=scene['end'],
                     prompt_version='v1',continuity_review='no_loop_boundary',recording_manifest=str(manifest.resolve()))
        rows = ev.db.execute('SELECT digest,summary_id,record FROM submissions').fetchall()
        if len(rows)>1:
            raise ValueError('Only one Hafnia submission allowed per incident')
        if rows and not rows[0][1]:
            raise ValueError('Unknown Hafnia submission outcome: reconcile history; never retry')
        gateway = Gateway()
        terminal_login(gateway)
        if rows:
            digest, summary_id, saved = rows[0]
            record = json.loads((root/'hafnia'/(digest+'.json')).read_text())
            if record['entry'] != entry:
                raise ValueError('Saved Hafnia request differs from this incident')
            record['summary'] = dict(Id=summary_id)
        else:
            digest,record = ev.submit(gateway,entry)
        record = ev.poll(gateway,digest,record,timeout=60)
        record_path = root/'hafnia'/(digest+'.json')
        evidence = assemble(cv_path,manifest,record_path,a.spatial)
        write(root/'joined.json',evidence)
        # Retain one frozen preview rather than changing event creation time on resume.
        old = root/'proposal.json'
        created = json.loads(old.read_text())['event_created_utc'] if old.exists() else None
        payload, meta = proposal(evidence,created)
        meta['evidence_sha256'] = sha(root/'joined.json')
        (root/'proposal.xml').write_bytes(payload)
        write(old,meta)
        from review_sidewalk import export
        export(root/'joined.json',manifest,root/'review')
        print('Review:',root/'review/index.html')
        print('Dispatch review ready:',meta['dispatch_review_ready'])
        print('Exact XML SHA-256:',meta['xml_sha256'])
        print('Stopped for operator review. No event sent.')
    finally:
        ev.db.close()


def dispatch(a, root):
    e = json.loads((root/'joined.json').read_text())
    meta = json.loads((root/'proposal.json').read_text())
    payload = (root/'proposal.xml').read_bytes()
    if not meta['dispatch_review_ready'] or not e.get('dispatch_review_ready'):
        raise ValueError('Fresh evidence gates not met; retrospective repair cannot authorize dispatch')
    if sha(root/'joined.json') != meta['evidence_sha256'] or hashlib.sha256(payload).hexdigest()!=meta['xml_sha256']:
        raise ValueError('Evidence or XML changed; rebuild and review')
    if sha(a.spatial) != e['spatial_sha256'] or spatial_config(a.spatial,SCOOTER).get('approved') is not True:
        raise ValueError('Approved camera-specific polygon changed or missing')
    print(payload.decode('utf-8'))
    print('SHA-256:',meta['xml_sha256'])
    if input('Type CONFIGURED after verifying the dedicated scooter-only alarm definition: ') != 'CONFIGURED':
        raise ValueError('Dedicated configuration not confirmed')
    if input('Type REVIEWED after reviewing this recording and potential incident: ') != 'REVIEWED':
        raise ValueError('Incident review pending')
    approval = input('Explicit dispatch approval: paste the complete XML SHA-256: ').strip().lower()
    if approval != meta['xml_sha256']:
        raise ValueError('Exact dispatch digest approval missing')
    ledger = Ledger(a.ledger)
    try:
        # Transactional reservation rejects overlapping windows across prompt variants
        # and different roots. A crash leaves a reservation for manual reconciliation.
        ledger.db.execute('CREATE TABLE IF NOT EXISTS sidewalk_episodes (key TEXT PRIMARY KEY,camera TEXT,start REAL,end REAL)')
        start,end = [datetime.fromisoformat(v.replace('Z','+00:00')).timestamp() for v in e['interval_utc']]
        with ledger.db:
            ledger.db.execute('BEGIN IMMEDIATE')
            overlaps = ledger.db.execute('SELECT key FROM sidewalk_episodes WHERE camera=? AND start<? AND end>?',
                                         (SCOOTER,end,start)).fetchall()
            if overlaps:
                raise ValueError('Episode already reserved; reconcile existing outcome, no automatic retry')
            # Include prior events from the existing persistent dispatch ledger.
            for row in ledger.db.execute('SELECT payload FROM analytics_dispatches'):
                xml = ET.fromstring(row[0]); ns = {'m':NS}
                camera = xml.findtext('.//m:Source/m:FQID/m:ObjectId',namespaces=ns)
                first = xml.findtext('m:StartTime',namespaces=ns)
                last = xml.findtext('m:EndTime',namespaces=ns)
                if camera and camera.lower()==SCOOTER and first and last:
                    fs,ls = [datetime.fromisoformat(v.replace('Z','+00:00')).timestamp() for v in (first,last)]
                    if fs<end and ls>start:
                        raise ValueError('Overlapping dispatch already exists; review persistent ledger')
            ledger.db.execute('INSERT INTO sidewalk_episodes VALUES (?,?,?,?)',(meta['dispatch_key'],SCOOTER,start,end))
        result = send(ledger,meta['dispatch_key'],payload,a.target,approval)
        write(root/'acceptance.json',result)
        print('Event Server result:',result['state'],'; verify native alarm separately.')
        if result['state']=='accepted':
            alarm_id=input('After Smart Client verification, enter new sidewalk alarm ID (blank if unverified): ').strip()
            if alarm_id:
                write(root/'operator-alarm.json',dict(alarm_id=alarm_id,camera_guid=SCOOTER,
                    xml_sha256=approval,verified_at=datetime.now(timezone.utc).isoformat(),
                    overlay_observation=input('Actual native object overlay observation: ')))
    finally:
        ledger.close()


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('stage',choices=['acquire','analyze','run','dispatch'])
    p.add_argument('--root',type=Path,required=True,help='Stable private incident directory; reuse to resume')
    p.add_argument('--spatial',type=Path,help='Camera-specific reviewed spatial.local.json')
    p.add_argument('--ssh-user',default='ubuntu')
    p.add_argument('--identity',type=Path)
    p.add_argument('--linux-python',default='/home/ubuntu/hafnia-hackathon-2026/.venv/bin/python')
    p.add_argument('--ledger',type=Path,help='Existing persistent native dispatch SQLite ledger (required for send)')
    p.add_argument('--target',default='127.0.0.1:9090')
    a=p.parse_args()
    root=a.root.resolve()
    if root.is_relative_to(REPO) and not root.is_relative_to(REPO/'runs'):
        p.error('Private incident output must be in ignored runs/ or outside repository')
    root.mkdir(parents=True,exist_ok=True)
    if a.stage in {'run','acquire'}:
        if not list((root/'acquisition').glob('*/manifest.json')):
            run(['powershell','-NoProfile','-File',REPO/'scripts/acquire_recording.ps1',
                 '-CameraName',CAMERA,'-Seconds','15','-Interval','1','-Mkv','-OutRoot',root/'acquisition'])
        print('Acquired recording: inspect snapshots/MKV before analysis.')
    if a.stage in {'run','analyze','dispatch'} and not a.spatial:
        p.error('--spatial is required')
    if a.stage in {'run','analyze'}:
        analyze(a,root)
    if a.stage=='dispatch':
        if not a.ledger or not a.ledger.exists():
            p.error('--ledger must identify the existing persistent native dispatch ledger')
        dispatch(a,root)


if __name__=='__main__':
    main()
