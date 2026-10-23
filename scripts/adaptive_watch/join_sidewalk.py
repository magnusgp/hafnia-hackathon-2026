"""Offline, same-recording join. Raw responses and outputs must remain private."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adaptive_watch.obstruction import measure, seconds
from adaptive_watch.evaluation import parse_result
from scene_contracts.gateway import video_uri


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('cv',type=Path)
    p.add_argument('--evaluations',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--model-audit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    cv=json.loads(a.cv.read_text())
    audit=json.loads(a.model_audit.read_text())
    models=[m for m in audit['models'] if m['resolved_revision'].startswith(cv['model_revision'])]
    if len(models)!=1:
        raise ValueError('Model revision audit missing or ambiguous')
    cv['model_file_provenance']=models[0]
    scene=cv['scene']
    original=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    if digest(a.manifest)!=cv['manifest_sha256'] or original!=cv['source_manifest']:
        raise ValueError('Original manifest differs from CV provenance')
    start,end=map(lambda v:datetime.fromisoformat(v.replace('Z','+00:00')),(scene['start'],scene['end']))
    expected=video_uri(original['camera_id'],start,end)
    joined=[]
    for path in sorted(a.evaluations.glob('*.json')):
        raw=json.loads(path.read_text())
        if raw.get('entry',{}).get('scene')!=scene['name'] or raw['entry'].get('camera_id','').lower()!=original['camera_id'].lower():
            continue
        req=raw['request']; summary=raw['summary']
        returned=summary.get('Request',{})
        extra=set(returned)-set(req)
        if (req.get('VideoUris')!=[expected] or any(returned.get(k)!=v for k,v in req.items())
                or extra-{'AiModelId'} or 'PromptId' in req
                or ('AiModelId' in extra and returned['AiModelId']!='traffic-general')):
            raise ValueError('Camera, interval or exact request mismatch')
        if raw.get('manifest_sha256')!=cv['manifest_sha256']:
            raise ValueError('Hafnia manifest hash mismatch')
        parsed=parse_result(summary)
        joined.append(dict(summary_id=summary['Id'],request=req,returned_request=returned,
            gateway_request_enrichment='traffic-general default AiModelId retained; exact submitted fields matched',
            original_response=summary.get('Response'),
            parsed=parsed,source_sha256=digest(path),original_saved_parse=raw.get('parsed'),
            strict_automatic_dispatch_valid=False,
            repair_provenance=parsed.get('normalizations',[])))
    if len(joined)!=2:
        raise ValueError('Expected exactly two same-recording prompt variants')
    measurements=measure(cv['observations'])
    for frame in cv['observations']:
        if not seconds(scene['start'])<=seconds(frame['timestamp_utc'])<seconds(scene['end']):
            raise ValueError('Sample outside exact assessment interval')
        source=next(f for f in original['frames'] if f['file']==frame['file'])
        if source['timestamp_utc']!=frame['timestamp_utc'] or digest(a.manifest.parent/frame['file'])!=frame['sha256']:
            raise ValueError('Frame identity mismatch')
    runs=measurements['qualifying_runs']
    first=runs[0]['first'] if runs else None
    before=[x for x in cv['observations'] if first and seconds(x['timestamp_utc'])<seconds(first)]
    during=[x for x in cv['observations'] if any(seconds(r['first'])<=seconds(x['timestamp_utc'])<=seconds(r['last']) for r in runs)]
    def stats(rows,key):
        values=[x['baseline'][key] for x in rows if x['baseline'][key] is not None]
        return dict(samples=len(values),minimum=min(values,default=None),maximum=max(values,default=None),
            above_fixed_one_percent=sum(v>.01 for v in values))
    result=dict(schema_version=1,camera_guid=original['camera_id'],camera_name=original['camera_name'],
        interval_utc=[scene['start'],scene['end']],manifest_sha256=cv['manifest_sha256'],
        cv_sha256=digest(a.cv),local_cv=cv,measurements=measurements,hafnia=joined,
        baseline_comparison={phase:{key:stats(rows,key) for key in ['frame_difference','reference_change']}
                             for phase,rows in [('before_stable_candidate',before),('stable_candidate',during)]},
        agreement='Both Hafnia prompts support a left object; CV measures a bounded stationary foreground hypothesis.',
        proposed_operator_decision='review_recording_and_approve_walkway' if measurements['candidate'] else 'insufficient_local_evidence',
        automatic_dispatch_eligible=False,
        limitations=cv['limitations']+measurements['limitations']+[
            'Hafnia action support does not measure exact spatial overlap or persistence.',
            'All normalized or repaired responses remain retrospective only in this join.',
            'Threshold changed from 50% to 10% box overlap after scooter inspection; same-clip calibration, not validation.',
            'Pre-event checks are technical checks from the same cycle; not independent negative examples.',
            'No precise entry/exit inferred from first/last detection; last sample is right-censored.'])
    a.out.write_text(json.dumps(result,indent=2))
    print(scene['name'],measurements['qualifying_runs'],result['baseline_comparison'])


if __name__=='__main__':
    main()
