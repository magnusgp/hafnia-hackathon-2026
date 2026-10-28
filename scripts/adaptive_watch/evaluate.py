"""User-launched, resumable sixteen-request batch. Private artifacts only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adaptive_watch.evaluation import Evaluation, prompt
from scene_contracts.gateway import Gateway, video_uri
from datetime import datetime


def main():
    p = argparse.ArgumentParser()
    p.add_argument('plan', type=Path)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if a.root.resolve().is_relative_to(repo):
        p.error('Private output must be outside the Git working tree')
    entries = json.loads(a.plan.read_text(encoding='utf-8-sig'))
    if len(entries) != 16:
        p.error('Exactly the authorized sixteen entries are required')
    prepared = []
    cameras = json.loads((repo/'cameras.local.json').read_text(encoding='utf-8-sig'))
    ids = {str(c['Id']).lower() for c in cameras}
    for entry in entries:
        if entry['camera_id'].lower() not in ids:
            p.error('Camera absent from verified local catalog')
        start, end = [datetime.fromisoformat(entry[k].replace('Z','+00:00')) for k in ('start','end')]
        payload = dict(Prompt=prompt(entry['scene'], entry['prompt_version']), VideoUris=[video_uri(entry['camera_id'],start,end)])
        digest = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        m = json.loads(Path(entry['recording_manifest']).read_text(encoding='utf-8-sig'))
        if m['camera_id'].lower() != entry['camera_id'].lower() or not (datetime.fromisoformat(m['requested_start_utc'].replace('Z','+00:00')) <= start < end <= datetime.fromisoformat(m['requested_end_utc'].replace('Z','+00:00'))):
            p.error('Recording provenance mismatch')
        prepared.append((entry,digest))
    if len({d for _,d in prepared}) != 16:
        p.error('Duplicate requests in plan')
    print('Validated sixteen requests; no native event operations.')
    if not a.apply:
        return
    ev = Evaluation(a.root)
    plan_hash = hashlib.sha256(a.plan.read_bytes()).hexdigest()
    lock = a.root/'plan.sha256'
    if lock.exists() and lock.read_text() != plan_hash:
        p.error('This output directory belongs to another plan')
    lock.write_text(plan_hash)
    gateway = Gateway()
    gateway.authenticate(interactive_only=True)
    rows = []
    for entry,digest in prepared:
        old = ev.db.execute('SELECT summary_id FROM submissions WHERE digest=?',(digest,)).fetchone()
        if old and not old[0]:
            rows.append(dict(scene=entry['scene'], digest=digest, status='submission_ambiguous'))
            continue
        try:
            if old:
                record = json.loads((a.root/(digest+'.json')).read_text())
                record['summary'] = dict(Id=old[0])
            else:
                _,record = ev.submit(gateway,entry)
            record = ev.poll(gateway,digest,record)
            status = record.get('poll_outcome') or record['summary']['Progress']
            if status == 'Completed' and 'evidence' not in record['parsed']:
                status = 'malformed_response'
        except TimeoutError:
            status = 'timeout'
        except Exception as exc:
            status = 'request_error_'+type(exc).__name__
        rows.append(dict(scene=entry['scene'], prompt_version=entry['prompt_version'], digest=digest,status=status))
        (a.root/'aggregate.json').write_text(json.dumps(dict(requests=rows,counts=dict(Counter(r['status'] for r in rows)), limitations=['Prompt variants and repeated camera loops are correlated; no independent accuracy estimate.','No native events authorized or sent.']),indent=2))
        print(len(rows),status,flush=True)

if __name__ == '__main__':
    main()
