"""Join same-recording CV and Hafnia evidence conservatively; never dispatch events."""
from datetime import datetime
import hashlib
import json

from scene_contracts.gateway import video_uri
from .evaluation import parse_result


def join_evidence(cv, evaluation=None):
    m=cv['source_manifest']
    record=dict(schema_version=1,camera_guid=m['camera_id'],camera_name=m['camera_name'],
        recording=dict(source=m['source'],requested_start_utc=m['requested_start_utc'],
                       requested_end_utc=m['requested_end_utc'],manifest_sha256=cv['manifest_sha256'],
                       first_observation_utc=cv['observations'][0]['timestamp_utc'],
                       last_observation_utc=cv['observations'][-1]['timestamp_utc'],
                       mkv_export=m.get('mkv_export'),recording_sequences=m.get('recording_sequences')),
        local_cv=cv, hafnia=None,combined_decision='incomplete_evidence',event_metadata=None,
        limitations=list(cv['limitations'])+['Neither model output establishes an incident as fact.'])
    if evaluation is None:
        record['limitations'].append('Hafnia assessment unavailable; no hybrid decision or event eligible.')
        return record
    request=evaluation['request']
    expected_uri=video_uri(m['camera_id'],datetime.fromisoformat(m['requested_start_utc'].replace('Z','+00:00')),
                           datetime.fromisoformat(m['requested_end_utc'].replace('Z','+00:00')))
    item=evaluation['summary']
    if ('PromptId' in request or request.get('VideoUris') != [expected_uri]
            or item.get('Request') != request):
        raise ValueError('Cannot join mismatched camera, interval, prompt, or gateway request provenance')
    if evaluation.get('manifest_sha256') != cv['manifest_sha256']:
        raise ValueError('Recording manifest hash mismatch')
    parsed=parse_result(item)
    record['hafnia']=dict(summary_id=item['Id'],prompt=request['Prompt'],response=item.get('Response'),
        progress=item.get('Progress'),failure_reason=item.get('LastError'),parsed=parsed,
        request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest())
    has_cv=any(t['observed_zone_s']>=2 for t in cv['tracks'])
    if item.get('Progress') != 'Completed':
        record['combined_decision']='analysis_failed_or_pending'
    elif has_cv and parsed['outcome']=='supported':
        record['combined_decision']='candidate_for_human_review'
    else:
        record['combined_decision']='insufficient_or_discordant_evidence'
    record['limitations'].append('Provisional zone, footpoint bias and track fragmentation must be reviewed before event eligibility.')
    return record
