"""Offline provenance audit and explicit AI review of the completed REL26-D campaign.

No network, inference, threshold fitting or reference-label edits. Review codes below
describe response claims, not validated event accuracy or automatic semantic parsing.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from collections import Counter
from datetime import datetime
from reliability_runner import digest, verify_availability, validate_age
from scene_contracts.gateway import video_uri

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def review(entry,text):
    scene,family,repeat = entry['scene'],entry['family'],entry['repeat']
    result = dict(review_mode='AI response review against accepted AI demo reference',
        person_recognized=True, broad_setting_recognized=True,
        movement_described=True, chronological_progression_described=True,
        temporal_accuracy='not_validated; narrative sequence is not ground-truth timing',
        explicit_internal_contradiction=False, incident_decision=None,
        contact_or_tool_detail_accuracy='not independently established')
    if scene == 'railway':
        positive = family == 'separate' or family == 'inventory' and repeat == 1
        result['target_claim'] = 'asserts_entry_or_occupancy' if positive else 'platform_only_or_denies_entry'
        result['recognition_assessment'] = 'partial_recovery_with_spatial_or_timing_errors' if positive else 'reference_disagreement_about_location_or_descent'
        result['conclusion_assessment'] = 'No separate incident outcome; review action claims and their supporting description'
        if family == 'separate':
            quote='Body moving down past the platform edge: observed.'
            result['caveat']='Calls standing-to-crouching and legs extended over tracks entry evidence at 3–9s; reviewed descent is about 10s and clear occupancy about 10.5s. Positive wording is not accurate transition timing.'
        elif family == 'inventory' and repeat == 1:
            quote='lower themselves onto the track area'
            result['caveat']='Explicit track-area wording, but describes sitting and subsequent walking toward the waiting area; not a fully faithful account or validated timing recovery.'
        elif family == 'spatial':
            quote='they crouch and sit on the platform edge'
            assert 'The person is not sitting at the edge' in text
            result['explicit_internal_contradiction']=True
            result['caveat']='Says sit on platform edge, then says not sitting at edge; also explicitly denies lower limbs below platform top.'
        elif family == 'direct':
            quote='No movement from the platform top down into the railway track area is visible.'
            result['caveat']='Explicit No agrees with its platform-only narrative but conflicts with reviewed descent/occupancy; output supports a spatial/action-description miss, not an isolated final-label error.'
        elif family == 'open':
            quote='walks along the platform toward the right'
            result['caveat']='Recognizes the red-clothed person and platform, but describes remaining on platform after sitting.'
        else:
            quote='platform surface' if family == 'sequence' else 'sit on the platform edge near the tracks'
            result['caveat']='Narrative describes platform sitting/crouching and rising; no recovered descent into track area.'
    else:
        tentative = family == 'open'
        absent = family == 'inventory' and repeat == 1
        result['target_claim']='handling_unspecified' if absent else 'handling_tentative' if tentative else 'handling_explicit'
        result['recognition_assessment']='omitted_contact_not_an_explicit_denial' if absent else 'handling_described; fine hand/tool details unverified'
        result['conclusion_assessment']='No explicit handling-versus-conclusion contradiction found'
        result['caveat']='Tool identity, exact hand use, successful opening, forced entry and intent are not established by the reference.'
        if family == 'open': quote='appearing to inspect or work on the lock'
        elif family == 'inventory': quote='lowering the tool toward the ground' if repeat == 1 else 'uses it to work on the padlock'
        elif family == 'sequence': quote='engage the latch with the tool' if repeat == 1 else 'positions the tool against the padlock'
        elif family == 'direct': quote='Yes.'
        elif family == 'spatial': quote='The right hand is in contact with the latch and the tool'
        else: quote='Hand contact or handling of the gate or latch area: observed.'
        if family in {'direct','separate'}:
            result['opening_assessment']='r01 explicitly no opening' if family == 'direct' and repeat == 1 else 'r02 does not assess opening' if family == 'direct' else 'opening explicitly not observed'
    assert quote in text, (entry['experiment_id'],quote)
    result['evidence_excerpt']=quote
    return result


def main():
    private=ROOT/'runs/reliability-diagnostics'
    batch=private/'operator-batch'
    plan=read(private/'execution-plan-v1.private.json')
    matrix_path=ROOT/'docs/reliability/diagnostic-24-matrix.json'
    matrix=read(matrix_path)
    signoff=read(private/'signoff-v1.private.json')
    assert sha(Path(signoff['review_artifact'])) == signoff['review_artifact_sha256']
    assert sha(ROOT/'docs/reliability/label-definitions.json') == signoff['definitions_sha256']
    assert digest(plan) == (batch/'plan.sha256').read_text() == digest(read(batch/'plan.private.json'))
    coverage=read(private/'recording-availability.private.json')
    proof=read(batch/'execution-preflight.private.json')
    assert proof['plan_sha256'] == digest(plan) and proof['authentication']=='successful_history_read'
    assert proof['new_requests']==24 and proof['remaining'] >= 44
    db=sqlite3.connect(f'file:{(batch/"reliability-ledger.sqlite3").as_posix()}?mode=ro',uri=True)
    try:
        rows=db.execute('SELECT experiment,summary_id,state,payload,result FROM requests ORDER BY rowid').fetchall()
    finally:
        db.close()
    assert len(rows)==len(plan)==len(matrix['experiments'])==24
    assert len({row[0] for row in rows})==len({row[1] for row in rows})==24
    results=[]
    for row,entry,definition in zip(rows,plan,matrix['experiments']):
        experiment,sid,state,payload,stored=row
        payload,stored=json.loads(payload),json.loads(stored)
        raw,parsed=stored['raw'],stored['parsed']
        assert experiment==entry['experiment_id']==definition['experiment_id']
        assert payload['Prompt']==entry['prompt']==definition['prompt']
        assert text_sha(payload['Prompt'])==entry['prompt_sha256']==definition['prompt_sha256']
        assert entry['original_matrix_sha256']==sha(matrix_path)
        assert entry['label_review_sha256']==signoff['review_artifact_sha256']
        assert set(payload)=={'Prompt','VideoUris'}
        assert payload['VideoUris']==[video_uri(entry['camera_id'],
            datetime.fromisoformat(entry['start'].replace('Z','+00:00')),
            datetime.fromisoformat(entry['end'].replace('Z','+00:00')))]
        assert raw['Request']['Prompt']==payload['Prompt'] and raw['Request']['VideoUris']==payload['VideoUris']
        assert raw['Id']==sid and raw['Progress']=='Completed' and state=='valid_descriptive_response'
        assert parsed['literal_response']==raw['Response'] and parsed['outcome'] is None
        assert read(batch/(experiment+'.submission.private.json'))['Id']==sid
        created=datetime.fromisoformat(raw['CreationTimeUtc'].replace('Z','+00:00'))
        validate_age(entry,now=created)
        verify_availability(entry,coverage,now=created)
        manifest_path=Path(entry['recording_manifest']); manifest=read(manifest_path)
        assert sha(manifest_path)==entry['manifest_sha256']
        assert manifest['camera_id'].lower()==entry['camera_id'].lower()
        assert sha(manifest_path.parent/manifest['mkv_export']['file'])==manifest['mkv_export']['sha256']
        for frame in manifest['frames']:
            assert sha(manifest_path.parent/frame['file'])==frame['sha256']
        results.append(dict(experiment_id=experiment,summary_id=sid,scene=entry['scene'],family=entry['family'],
            repeat=entry['repeat'],prompt_sha256=entry['prompt_sha256'],payload_sha256=digest(payload),
            uri_sha256=text_sha(payload['VideoUris'][0]),camera_guid_sha256=text_sha(entry['camera_id'].lower()),
            start=entry['start'],end=entry['end'],source_manifest_sha256=entry['manifest_sha256'],
            video_sha256=manifest['mkv_export']['sha256'],reference_sha256=entry['label_review_sha256'],
            gateway_status=raw['Progress'],summary_created=raw['CreationTimeUtc'],summary_completed=raw['LastUpdatedTimeUtc'],
            actual_model=raw['Request']['AiModelId'],parse_status=state,response_sha256=text_sha(raw['Response']),
            returned_envelope_sha256=digest(raw),response_review=review(entry,raw['Response'])))
    # Check prior original files without rewriting or re-parsing any of them.
    historical=read(ROOT/'runs/reliability-20261026/saved-response-audit.private.json')
    for item in historical:
        assert sha(Path(item['source']))==item['source_sha256']
    prior=read(ROOT/'results/reliability/eight-request-audit.json')['evaluations']
    olddb=sqlite3.connect(f'file:{(ROOT/"runs/reliability-fresh/operator-batch/reliability-ledger.sqlite3").as_posix()}?mode=ro',uri=True)
    try:
        oldrows=olddb.execute('SELECT summary_id,result FROM requests').fetchall()
    finally:
        olddb.close()
    for sid,stored in oldrows:
        old=next(item for item in prior if item['summary_id']==sid)
        assert text_sha(json.loads(stored)['raw']['Response'])==old['response_sha256']
    pairs=[]
    for scene in ('railway','gate'):
        for family in ('open','inventory','sequence','direct','spatial','separate'):
            pair=[r for r in results if r['scene']==scene and r['family']==family]
            assert len(pair)==2 and pair[0]['payload_sha256']==pair[1]['payload_sha256']
            pairs.append(dict(scene=scene,family=family,
                target_claims=[r['response_review']['target_claim'] for r in pair],
                claim_category_agrees=pair[0]['response_review']['target_claim']==pair[1]['response_review']['target_claim'],
                literal_text_identical=pair[0]['response_sha256']==pair[1]['response_sha256']))
    output=dict(batch='REL26-D',actual_submissions=24,completed_requests=24,
        gateway_status_counts=dict(Counter(r['gateway_status'] for r in results)),
        model_counts=dict(Counter(r['actual_model'] for r in results)),
        original_historical_files_verified=len(historical),prior_REL26_B_responses_verified=len(oldrows),
        distinct_loop_families=2,independent_new_events=0,eligible_distinct_task_matched_negatives=0,
        semantic_counts={scene:dict(Counter(r['response_review']['target_claim'] for r in results if r['scene']==scene)) for scene in ('railway','gate')},
        explicit_self_contradictory_responses=sum(r['response_review']['explicit_internal_contradiction'] for r in results),
        paired_claim_agreement=sum(p['claim_category_agrees'] for p in pairs),paired_comparisons=len(pairs),
        paired_identical_text=sum(p['literal_text_identical'] for p in pairs),repeats=pairs,results=results,
        request_window=[results[0]['summary_created'],results[-1]['summary_completed']],
        source_and_prompt_audit='passed_all_24; age and coverage freshness checked at each actual creation time',
        preflight=dict(checked_at=proof['checked_at'],available_quota=proof['remaining'],new_requests=proof['new_requests']),
        decision='NO-GO for validated independent verification; GO for a qualified disagreement demonstration',
        limitations=['Accepted AI demo reference review, not independently attested human labels',
            'Response review is explicit qualitative AI review, not a validated semantic classifier',
            'Action claims and within-loop repeat agreement are not event-level accuracy estimates',
            'No gateway-consumed frames, internal sampling or backend weights available',
            'Railway positive wording contains timing/spatial errors; no robust fully faithful recovery established',
            'No new pose inference, independent CV test or model training; proximity remains separate from entry',
            'HTTP transport status not saved; Completed is gateway analysis status',
            'All further inference stopped after the authorized 24'])
    target=ROOT/'results/reliability/completed-diagnostic-24.json'
    target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Audited 24 completed requests, 24 unique summary IDs, exact source/prompt echoes; no network calls')
    print(json.dumps(output['semantic_counts']))
    print('Repeat claim agreement:',output['paired_claim_agreement'],'/12; exact text:',output['paired_identical_text'],'/12')


if __name__=='__main__':
    main()
