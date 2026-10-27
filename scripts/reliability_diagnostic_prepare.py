"""Read-only evidence audit and diagnostic prompt preparation. No network/inference."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def sheets():
    sys.path.insert(0, str(ROOT/'runs/reliability-fresh/decode-deps'))
    from PIL import Image, ImageDraw
    for path in (ROOT/'runs/reliability-diagnostics').glob('*/*/manifest.json'):
        m = read(path)
        sheet = Image.new('RGB', (1920,160*((len(m['frames'])+7)//8)))
        draw = ImageDraw.Draw(sheet)
        for i,f in enumerate(m['frames']):
            assert sha(path.parent/f['file']) == f['sha256']
            x,y=i%8*240,i//8*160
            sheet.paste(Image.open(path.parent/f['file']).resize((240,139)),(x,y))
            draw.text((x,y+140),f"{i} {f['timestamp_utc'][11:23]}",fill='white')
        sheet.save(path.parent/'review.jpg')
        print(path.parent.name)


def audit():
    original = read(ROOT/'runs/reliability-20261026/saved-response-audit.private.json')
    records = []
    for a in original:
        assert sha(Path(a['source'])) == a['source_sha256']
        e=a['entry']
        if e['scene'] == e['camera_name'] and e['scene'] in {'person_on_railway_tracks','school_gate_break_in_night'}:
            records.append((e['scene']+'-'+e['prompt_version'],a['original_request'],a['original_summary'],a['parsed']))
    db=sqlite3.connect('file:'+(ROOT/'runs/reliability-fresh/operator-batch/reliability-ledger.sqlite3').as_posix()+'?mode=ro',uri=True)
    for e,p,r in db.execute('select experiment,payload,result from requests order by experiment'):
        r=json.loads(r)
        records.append((e,json.loads(p),r['raw'],r['parsed']))
    db.close()
    assert len(records)==8
    private=[]; public=[]
    old_sources=read(ROOT/'runs/reliability-20261026/reviewed-ai-demo.json')['sources']
    fresh_plan=read(ROOT/'runs/reliability-fresh/execution-plan.private.json')
    from urllib.parse import urlsplit,parse_qs
    for e,p,r,parsed in records:
        assert p['Prompt']==r['Request']['Prompt'] and p['VideoUris']==r['Request']['VideoUris']
        assert 'PromptId' not in p
        uris=[]
        for uri in p['VideoUris']:
            u=urlsplit(uri); q=parse_qs(u.query)
            uris.append(dict(scheme=u.scheme,host=u.netloc,camera_sha256=hashlib.sha256(u.path.encode()).hexdigest(),start=q.get('StartTime'),end=q.get('EndTime'),uri_sha256=hashlib.sha256(uri.encode()).hexdigest()))
        row=dict(experiment_id=e,summary_id=r['Id'],prompt=p['Prompt'],payload_keys=list(p),
            payload_sha256=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),
            returned_request_keys=list(r['Request']),returned_model=r['Request'].get('AiModelId'),
            explicit_requested_model=p.get('AiModelId'),source=r.get('Source'),progress=r.get('Progress'),
            created=r.get('CreationTimeUtc'),updated=r.get('LastUpdatedTimeUtc'),
            response_sha256=hashlib.sha256(r['Response'].encode()).hexdigest(),
            returned_top_level_keys=list(r),uris=uris,parsed=parsed,
            source_information='Request URI echoed; no returned frame list, decoded video digest, sampling schedule or backend model version')
        public.append(row)
        scene='railway' if 'railway' in e else 'gate'
        if e.startswith('REL26-B-'):
            bound=next(b for b in fresh_plan if b['experiment_id']==e)
            mp=Path(bound['recording_manifest'])
            expected=bound['manifest_sha256']
        else:
            bound=next(b for b in old_sources if b['scene']==scene)
            mp=ROOT/Path(bound['manifest']); expected=bound['manifest_sha256']
        assert sha(mp)==expected
        row['source_manifest_sha256']=expected
        m=read(mp)
        row['local_source_video_sha256']=m.get('mkv_export',{}).get('sha256') or bound.get('video_sha256')
        private.append(dict(experiment_id=e,actual_payload=p,returned_summary=r))
    save(ROOT/'runs/reliability-diagnostics/eight-request-audit.private.json',private)
    discovery=ROOT/'runs/reliability-diagnostics/model-discovery.private.json'
    model_evidence=dict(live_alternatives_verified=False,installed_xml_sha256=sha(Path('C:/Program Files/Milestone XProtect Hafnia Integration Gateway/Hafnia.Vlm.Gateway.xml')),
                        installed_help_sha256=sha(Path('C:/Program Files/Milestone XProtect Hafnia Integration Gateway/wwwroot/site/search.json')))
    if discovery.exists():
        d=read(discovery)
        model_evidence.update(anonymous_read_checked_at=d['checked_at'],anonymous_read_status=d.get('status'),discovery_sha256=sha(discovery))
    save(ROOT/'results/reliability/eight-request-audit.json',dict(evaluations=public,original_files_hash_verified=len(original),models=sorted(set(r['returned_model'] for r in public)),model_discovery=model_evidence))
    print('Verified eight exact payload echoes and 16 immutable historical response hashes')


def matrix():
    suffix='\nUse only visible evidence in this video. Do not infer authorization, criminal intent or hidden actions. Mark occluded or unresolved details as unknown. Describe observations before interpretations. Give approximate relative times only when supported; otherwise say timing unknown. Do not use an incident label as a substitute for describing what is visible.'
    common={
      'open': 'Describe this video in your own words, including the setting, visible people and their actions from beginning to end.',
      'inventory': 'Inventory the visible people and objects. For each person give distinguishing clothing, location, posture and nearby objects. State which objects or body contacts cannot be resolved. Do not decide whether an incident occurred.',
      'sequence': 'Give a chronological sequence of visible changes. For the main moving person, describe starting location, intermediate postures and contacts, changes in height or position, and final location. Separate observed transitions from uncertain ones.'}
    special={
      'railway': {
        'direct': 'Does any person visibly move from the platform top down into the railway track area? Answer yes, no or unknown, then describe the evidence for the transition and subsequent position. Sitting near an edge alone does not establish entry.',
        'spatial': 'Identify the main moving person by clothing. Describe their position relative to the platform top, vertical platform edge and track bed at the start, middle and end. Are their feet or lower legs visibly below the platform top? Distinguish sitting at the edge, downward movement and standing or walking in the track area. State unknown where contact or depth cannot be resolved.',
        'separate': 'Assess each item separately as observed, not_observed or unknown: approach to the platform edge; sitting or crouching at the edge; body moving down past the platform edge; person occupying the track area afterwards. Give visible supporting or opposing evidence for each item. Do not make proximity sufficient for track entry.'},
      'gate': {
        'direct': 'Does any person visibly handle or manipulate the gate, latch or lock area? Answer yes, no or unknown, then describe hand or body contact and motion. Successful opening is not required for handling; do not assume a tool is present.',
        'spatial': 'Identify the main moving person by clothing and describe their position and posture near the gate. Describe visible hands, contact points and movement near the gate or latch at the start, middle and end. State whether any object in a hand is actually identifiable; otherwise say unknown.',
        'separate': 'Assess each item separately as observed, not_observed or unknown: approach to the gate; crouching near it; hand contact or handling of the gate or latch area; movement of the gate; gate opening. Give visible supporting or opposing evidence for each item. Handling does not require opening; do not infer a tool, forced entry or intent.'}}
    rows=[]
    for repeat in (1,2):
        for kind in ('open','inventory','sequence','direct','spatial','separate'):
            for scene in ('railway','gate'):
                prompt=(common.get(kind) or special[scene][kind])+suffix
                rows.append(dict(experiment_id=f'REL26-D-{scene}-{kind}-r{repeat:02}',scene=scene,family=kind,repeat=repeat,prompt=prompt,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),source_slot=scene+'-fresh-001',expected_model='traffic-general',model_response=None,parse_status='not_submitted'))
    assert len(rows)==24 and len({r['experiment_id'] for r in rows})==24
    for a,b in zip(rows[:12],rows[12:]):
        assert a['prompt']==b['prompt']
    freeze(ROOT/'docs/reliability/diagnostic-24-matrix.json',dict(batch='REL26-D',authorization='not_authorized',expected_requests=24,concurrency=1,design='2 scenes x 6 prompt families x 2 exact repetitions; fixed interleaved order',response_contract='Unconstrained text; retain verbatim. Separately extract recognition/action items as observed, not_observed, unknown or unparseable; do not run legacy incident parser on diagnostic prose.',experiments=rows))
    print('Prepared 24 diagnostic definitions; no execution or inference')


def models():
    # One anonymous read only; never use environment passwords or repeat logins.
    sys.path.insert(0,str(ROOT))
    from scene_contracts.gateway import Gateway, GatewayError
    result=dict(checked_at=datetime.now(timezone.utc).isoformat(),endpoint='/api/Models',login_attempts=0,inference_submissions=0)
    try:
        result['response']=Gateway().request('GET','/api/Models')
    except GatewayError as exc:
        result['status']=str(exc)
    save(ROOT/'runs/reliability-diagnostics/model-discovery.private.json',result)
    print(result.get('status','Model list saved privately'))


def freeze(path, value):
    if path.exists():
        assert read(path)==value, 'Frozen artifact differs; use a new version, never replace evidence'
    else:
        save(path,value)


def bind():
    from reliability_runner import validate, digest, Runner, verify_availability
    root=ROOT/'runs/reliability-diagnostics'
    specs=[('railway','person_on_railway_tracks_20261027T115538Z','2026-10-27T11:55:38Z','2026-10-27T11:55:51Z','railway-decoded'),
           ('gate','school_gate_break_in_night_20261027T115549Z','2026-10-27T11:55:49Z','2026-10-27T11:56:02Z','gate-final-decoded')]
    sources=[]; sanitized=[]
    for scene,directory,start,end,decode in specs:
        path=root/'selected'/directory/'manifest.json'; m=read(path)
        assert m['requested_start_utc']==start.replace('Z','.000Z') and m['requested_end_utc']==end.replace('Z','.000Z')
        frames=[]
        for i,f in enumerate(m['frames']):
            assert sha(path.parent/f['file'])==f['sha256']
            if scene=='railway':
                phase='platform_approach' if i<6 else 'edge_proximity_or_seated' if i<20 else 'visible_descent' if i==20 else 'track_occupancy'
                label='negative' if i<6 else 'ambiguous' if i<21 else 'positive'
            else:
                phase='approach' if i<6 else 'contact_transition' if i<11 else 'visible_handling'
                label='negative' if i<6 else 'ambiguous' if i<11 else 'positive'
            frames.append(dict(**f,index=i,phase=phase,reviewed_label=label,reviewer='Codex AI demo review'))
        video=path.parent/m['mkv_export']['file']; assert sha(video)==m['mkv_export']['sha256']
        decoded=read(root/(decode+'.json')); assert decoded['mkv_sha256']==sha(video)
        source=dict(scene=scene,event_id=scene+'-loop-001',manifest_sha256=sha(path),video_sha256=sha(video),frames=frames,
                    continuity_review='ai_reviewed_no_loop_boundary',decode_artifact_sha256=sha(root/(decode+'.json')),
                    review_basis='All decoded frames inspected in chronological sheet; selected snapshots and full-resolution transition frames reviewed',
                    pts_absolute_origin='unverified; gate export spans 13.9s for 13s request; no fabricated UTC join')
        sources.append(source)
        sanitized.append(dict(scene=scene,start=start,end=end,duration_s=13,manifest_sha256=sha(path),video_sha256=sha(video),snapshot_count=len(frames),decoded_frames=decoded['decoded_frames'],first_pts=decoded['pts_s'][0],last_pts=decoded['pts_s'][-1],continuity=source['continuity_review'],independent_new_events=0))
    review=dict(review_mode='ai_demo',definitions_sha256=sha(ROOT/'docs/reliability/label-definitions.json'),sources=sources,
        rejected_candidate=dict(scene='gate',start='2026-10-27T11:55:41Z',end='2026-10-27T11:55:54Z',reason='Person disappears across reset bracket 11:55:48.465-48.965; original retained'),
        boundary_brackets=dict(railway_next_reset=['2026-10-27T11:55:52.313Z','2026-10-27T11:55:52.813Z'],gate_previous_reset=['2026-10-27T11:55:48.465Z','2026-10-27T11:55:48.965Z']))
    rp=root/'reference-v1.private.json'; freeze(rp,review)
    signoff=dict(status='reviewed',review_mode='ai_demo',user_authorized_ai_review=True,reviewer='Codex AI demo review',definitions_sha256=review['definitions_sha256'],review_artifact=str(rp),review_artifact_sha256=sha(rp))
    sp=root/'signoff-v1.private.json'
    # Actual wall-clock review time, retained on subsequent offline reproductions.
    signoff['reviewed_at']=read(sp)['reviewed_at'] if sp.exists() else datetime.now(timezone.utc).isoformat()
    freeze(sp,signoff)
    matrix_path=ROOT/'docs/reliability/diagnostic-24-matrix.json'; matrix=read(matrix_path); plan=[]
    for row in matrix['experiments']:
        index=0 if row['scene']=='railway' else 1
        scene,directory,start,end,decode=specs[index]; source=sources[index]
        path=root/'selected'/directory/'manifest.json'; m=read(path)
        plan.append(dict(**row,stage='B',event_id=source['event_id'],prompt_version='diagnostic-'+row['family'],camera_id=m['camera_id'],start=start,end=end,
            source_recording_id='acquisition-sha256:'+sha(path),recording_manifest=str(path),manifest_sha256=sha(path),
            label_review_sha256=sha(rp),continuity_review=source['continuity_review'],original_matrix_sha256=sha(matrix_path),
            ground_truth=dict(scope='Visible descent and track occupancy' if scene=='railway' else 'Visible gate handling; opening and intent unestablished',review_mode='ai_demo'),response_contract='diagnostic_free_text'))
    prepared=list(validate(plan,signoff)); assert len(prepared)==24
    pp=root/'execution-plan-v1.private.json'; freeze(pp,plan)
    # Prepare only an empty persistent ledger; never reserve an inference claim here.
    runner=Runner(root/'operator-batch')
    assert runner.db.execute('select count(*) from requests').fetchone()[0]==0
    runner.db.close()
    coverage_path=root/'recording-availability.private.json'
    coverage=read(coverage_path) if coverage_path.exists() else None
    if coverage:
        for entry,_ in prepared:
            verify_availability(entry,coverage)
    save(ROOT/'results/reliability/diagnostic-recording-verification.json',dict(checked_at=datetime.now(timezone.utc).isoformat(),offline_preflight='passed_source_and_prompt_validation',expected_requests=24,submitted=0,plan_sha256=digest(plan),matrix_sha256=sha(matrix_path),sources=sanitized,
        recording_coverage='passed_all_24' if coverage else 'not_refreshed',coverage_sha256=sha(coverage_path) if coverage else None,
        submission_ready=False,blockers=['New batch not authorized','Live authenticated available-model list not obtained','Legacy incident parser must not interpret diagnostic prose as an incident-format error; response-mode adaptation required before execution','Refresh authenticated quota and exact coverage within 15 minutes before submission; enforce under-24h at each POST'],
        controls=dict(distinct_known_positive_families=2,additional_distinct_positives=0,eligible_distinct_task_matched_negatives=0),
        expires_before='2026-10-28T11:55:38Z'))
    print('24 source-bound definitions pass offline validation; empty persistent ledger; zero submissions')


if __name__=='__main__':
    if '--sheets' in sys.argv:
        sheets()
    elif '--models' in sys.argv:
        models()
    elif '--bind' in sys.argv:
        bind()
    else:
        audit(); matrix()
