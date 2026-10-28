"""Bind the unchanged four experimental definitions to reviewed fresh sources.

Selection is explicit and versioned, never inferred from new model responses.
No network calls or inference. Old annotations, plans and predictions are read-only.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from reliability_plan import REPO, read, sha, frozen_write
from reliability_runner import digest, validate


def prepare(root, railway, gate):
    matrix_path = REPO/'docs/research/reliability/first-batch-matrix.json'
    definitions = REPO/'docs/research/reliability/label-definitions.json'
    matrix = read(matrix_path)
    sources = []
    for name,path,start,end in [
        ('railway',railway,'2026-10-26T22:03:53Z','2026-10-26T22:04:06Z'),
        ('gate',gate,'2026-10-26T22:03:51Z','2026-10-26T22:04:03Z')]:
        m = read(path)
        if m['requested_start_utc'] != start.replace('Z','.000Z') or m['requested_end_utc'] != end.replace('Z','.000Z'):
            raise ValueError('Acquisition differs from reviewed selection')
        frames = []
        for i,f in enumerate(m['frames']):
            if sha(path.parent/f['file']) != f['sha256']:
                raise ValueError('Source frame changed')
            if name == 'railway':
                phase = ('platform_approach' if i<6 else 'edge_proximity' if i<8 else
                         'seated_edge_proximity' if i<20 else 'visible_descent' if i==20 else
                         'confirmed_entry' if i==21 else 'track_occupancy')
                label = 'negative' if i<8 else 'ambiguous' if i<21 else 'positive'
            else:
                phase = 'approach' if i<3 else 'contact_transition' if i==3 else 'visible_gate_manipulation'
                label = 'negative' if i<3 else 'ambiguous' if i==3 else 'positive'
            frames.append(dict(index=i,file=f['file'],timestamp_utc=f['timestamp_utc'],sha256=f['sha256'],
                               reviewed_label=label,phase=phase,reviewer='Codex AI visual review; authorized demo scope'))
        export=m['mkv_export']
        if sha(path.parent/export['file']) != export['sha256']:
            raise ValueError('Export changed')
        sources.append(dict(scene=name,event_id=name+'-loop-001',manifest=str(path.resolve()),
            manifest_sha256=sha(path),source_recording_id='acquisition-sha256:'+sha(path),
            recording_identity_kind='Hash-bound acquisition, not a claimed native XProtect recording GUID',
            camera_id=m['camera_id'],start=start,end=end,frames=frames,video_sha256=export['sha256'],
            recording_sequences=m['recording_sequences'],continuity_review='ai_reviewed_no_loop_boundary',
            ground_truth=dict(outcome='supported',scope='Visible descent/track presence' if name=='railway' else 'Visible gate handling/manipulation',
                              cannot_establish='Intent, authorization, successful opening or forced entry'),
            independence='Reacquired existing loop; same event family as October 22, not independent'))
    artifact = root/'fresh-review.private.json'
    frozen_write(artifact,dict(definitions_sha256=sha(definitions),sources=sources,review_mode='ai_demo',
        loop_review=dict(railway_next_reset_utc=['2026-10-26T22:04:06.813Z','2026-10-26T22:04:07.313Z'],
                         gate_reset_utc=['2026-10-26T22:04:03.865Z','2026-10-26T22:04:03.965Z'],
                         excluded_candidate='Gate 22:03:52-22:04:04 includes a reset; retained privately, never submitted'),
        notes=['Fresh selected contact sheets reviewed before any new inference.',
               'Gate reset tightened using full-resolution frame at 03.965; selected interval ends at 03.000.',
               'Sampled image review; MKV stream PTS does not establish absolute UTC independently.']))
    signoff = dict(status='reviewed',review_mode='ai_demo',user_authorized_ai_review=True,
                   reviewer='Codex AI visual review',definitions_sha256=sha(definitions),
                   review_artifact=str(artifact.resolve()),review_artifact_sha256=sha(artifact))
    signoff_path=root/'fresh-signoff.private.json'
    if signoff_path.exists():
        signoff['reviewed_at']=read(signoff_path)['reviewed_at']
    else:
        signoff['reviewed_at']=datetime.now(timezone.utc).isoformat()
    frozen_write(signoff_path,signoff)
    plan=[]
    old_plan=REPO/'runs/reliability-20261026/first-batch.private.json'
    import sqlite3
    old_ledger=old_plan.parent/'operator-batch/reliability-ledger.sqlite3'
    with sqlite3.connect('file:'+old_ledger.as_posix()+'?mode=ro',uri=True) as old_db:
        attempted=old_db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
    old_db.close()
    if attempted:
        raise ValueError('Original experiment IDs have submission claims; reconcile before rebinding sources')
    for spec in matrix['experiments']:
        source=next(s for s in sources if s['event_id']==spec['event_id'])
        plan.append(dict(experiment_id=spec['experiment_id'],stage='B',event_id=spec['event_id'],
            scene=spec['scene'],prompt_version=spec['prompt_version'],prompt=spec['body']+matrix['suffix'],
            camera_id=source['camera_id'],start=source['start'],end=source['end'],
            source_recording_id=source['source_recording_id'],recording_manifest=source['manifest'],
            manifest_sha256=source['manifest_sha256'],label_review_sha256=sha(artifact),
            continuity_review=source['continuity_review'],ground_truth=source['ground_truth'],
            original_matrix_sha256=sha(matrix_path),supersedes_unsubmitted_plan_sha256=sha(old_plan),
            model_response=None,parse_status='not_submitted'))
    prepared=list(validate(plan,signoff))
    frozen_write(root/'execution-plan.private.json',plan)
    report=dict(new_requests=len(plan),offline_preflight='passed',new_inference_submissions=0,
        source_recordings=len(sources),independent_new_events=0,plan_sha256=digest(plan),
        experiments=[dict(experiment_id=e['experiment_id'],start=e['start'],end=e['end'],
                         source_recording_id=e['source_recording_id'],request_sha256=digest(payload),
                         ground_truth=e['ground_truth'],parse_status='not_submitted') for e,payload in prepared],
        authenticated_preflight='pending operator terminal check',quota_contract='unverified',
        controls=dict(additional_requests=0,reason='No coherent 12-17-second task-matched negative event found in the acquired loops'))
    frozen_write(root/'offline-preflight.json',report)
    import json
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--railway-manifest',type=Path,required=True)
    p.add_argument('--gate-manifest',type=Path,required=True)
    a=p.parse_args()
    if not a.root.resolve().is_relative_to((REPO/'runs').resolve()):
        p.error('Private execution plans must stay under ignored runs/')
    prepare(a.root,a.railway_manifest,a.gate_manifest)
