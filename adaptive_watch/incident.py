"""Review-only incident assembly. No network calls or automatic dispatch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from adaptive_watch.obstruction import measure, seconds
from adaptive_watch.capabilities import camera_config
from scene_contracts.analytics_event import build, dispatch_key
from scene_contracts.gateway import video_uri


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spatial_config(path, camera):
    s = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if s['camera_guid'].lower() != camera.lower():
        raise ValueError('Spatial configuration belongs to another camera')
    polygon = s['polygon']
    if len(polygon) < 3 or any(len(p) != 2 or any(type(v) not in (int,float) or not 0 <= v <= 1 for v in p) for p in polygon):
        raise ValueError('Invalid normalized pedestrian polygon')
    if s.get('approved') is True and not (s.get('approved_by') and s.get('approved_at') and s.get('reference_frame_sha256')):
        raise ValueError('Approval requires operator, time and reference frame identity')
    return s


def box_overlap(box, polygon):
    """Exact image-space polygon/rectangle area; never physical clearance."""
    l,t,r,b = box
    if not 0 <= l < r <= 1 or not 0 <= t < b <= 1:
        raise ValueError('Invalid normalized box')
    points = list(polygon)
    for axis, edge, sign in [(0,l,1),(0,r,-1),(1,t,1),(1,b,-1)]:
        clipped = []
        if not points:
            return 0.0
        for a,c in zip(points[-1:]+points[:-1], points):
            ai, ci = sign*(a[axis]-edge)>=0, sign*(c[axis]-edge)>=0
            if ai != ci:
                u = (edge-a[axis])/(c[axis]-a[axis])
                clipped.append([a[0]+u*(c[0]-a[0]),a[1]+u*(c[1]-a[1])])
            if ci:
                clipped.append(c)
        points = clipped
    area = abs(sum(a[0]*c[1]-c[0]*a[1] for a,c in zip(points,points[1:]+points[:1])))/2
    return min(1.0, area/((r-l)*(b-t)))


def assemble(cv_path, manifest_path, record_path, spatial_path):
    cv = json.loads(Path(cv_path).read_text())
    m = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    record = json.loads(Path(record_path).read_text())
    scene = cv['scene']
    capability = camera_config(m['camera_name'], m['camera_id'])
    camera = capability['camera_guid']
    if scene['name'] != capability['name']:
        raise ValueError('CV scene and configured camera mismatch')
    if scene.get('queries') != capability['queries']:
        raise ValueError('CV object queries differ from camera capability')
    if cv['manifest_sha256'] != sha(manifest_path) or cv['source_manifest'] != m:
        raise ValueError('CV acquisition manifest identity mismatch')
    if record['manifest_sha256'] != sha(manifest_path):
        raise ValueError('Hafnia acquisition identity mismatch')
    if cv.get('execution_device') != 'cuda' or cv.get('execution_platform') != 'Linux':
        raise ValueError('Fresh evidence requires recorded Linux CUDA execution')
    if cv.get('host','').split('.')[0] != 'p022-linux':
        raise ValueError('Fresh CV must execute on p022-linux')
    entry = record['entry']
    if entry.get('continuity_review') != 'no_loop_boundary':
        raise ValueError('Operator continuity review missing')
    if any(entry[k] != scene[k] for k in ('start','end')) or entry['camera_id'].lower() != camera:
        raise ValueError('CV and Hafnia interval/camera mismatch')
    dt = lambda x: datetime.fromisoformat(x.replace('Z','+00:00'))
    if not dt(m['requested_start_utc']) <= dt(scene['start']) < dt(scene['end']) <= dt(m['requested_end_utc']):
        raise ValueError('Analysis interval outside original recording')
    if any(dt(scene[k]).microsecond for k in ('start','end')):
        raise ValueError('Hafnia requires exact whole-second analysis bounds')
    if not cv['observations']:
        raise ValueError('No localized samples')
    expected = video_uri(camera, dt(scene['start']), dt(scene['end']))
    req, summary = record['request'], record['summary']
    returned = summary.get('Request',{})
    extras = set(returned)-set(req)
    if req['VideoUris'] != [expected] or any(returned.get(k) != v for k,v in req.items()) or extras-{'AiModelId'}:
        raise ValueError('Exact submitted/returned Hafnia request mismatch')
    if 'AiModelId' in extras and returned['AiModelId'] != 'traffic-general':
        raise ValueError('Unknown gateway enrichment')
    if summary.get('Progress') != 'Completed' or not summary.get('Id'):
        raise ValueError('Hafnia assessment not complete')
    spatial = spatial_config(spatial_path, camera)
    known = {f['file']:f for f in m['frames']}
    if spatial.get('approved') is True and spatial['reference_frame_sha256'] not in {f.get('sha256') for f in m['frames']}:
        raise ValueError('Approved reference frame is not in this recording')
    last = None
    for row in cv['observations']:
        source = (Path(manifest_path).parent/row['file']).resolve()
        if not source.is_relative_to(Path(manifest_path).parent.resolve()):
            raise ValueError('Frame path escapes acquisition directory')
        f = known[row['file']]
        now = seconds(row['timestamp_utc'])
        if not seconds(scene['start']) <= now < seconds(scene['end']) or last is not None and now <= last:
            raise ValueError('Samples outside interval or unordered')
        if f['timestamp_utc'] != row['timestamp_utc'] or sha(source) != row['sha256'] or f.get('sha256') != row['sha256']:
            raise ValueError('Original timestamped frame identity mismatch')
        last = now
        for obj in row['objects']:
            obj['box_walkway_overlap'] = box_overlap(obj['box'], spatial['polygon'])
    cv['scene']['walkway'] = spatial['polygon']
    cv['scene']['walkway_approved'] = spatial.get('approved') is True
    measurements = measure(cv['observations'], **capability['temporal_policy'])
    from adaptive_watch.evaluation import parse_result
    parsed = parse_result(summary)
    strict = parsed.get('category') == 'valid_model_decision' and not parsed.get('normalizations')
    ready = spatial.get('approved') is True and strict and parsed.get('outcome') == 'supported' and measurements['candidate']
    return dict(schema_version=2, camera_guid=camera, capability=capability['capability'], capability_config=capability, evidence_kind='fresh_analysis', camera_name=m['camera_name'],
                interval_utc=[scene['start'],scene['end']], manifest_sha256=sha(manifest_path),
                cv_sha256=sha(cv_path), spatial_sha256=sha(spatial_path), spatial=spatial,
                local_cv=cv, measurements=measurements,
                hafnia=[dict(summary_id=summary['Id'], original_response=summary.get('Response'),
                             request=req, returned_request=returned, parsed=parsed,
                             source_sha256=sha(record_path), repair_provenance=parsed.get('normalizations',[]))],
                agreement=('Semantic support and sampled CV candidate agree; clearance remains operator judgment.' if ready
                           else 'Uncertainty or an approval/strict-response gate remains; inspect both components.'),
                proposed_operator_decision='operator_incident_review_required' if ready else 'blocked_pending_review',
                dispatch_review_ready=ready, automatic_dispatch_eligible=False,
                limitations=cv['limitations']+measurements['limitations']+[
                    'Same-clip geometry and thresholds are not independently validated.',
                    'Synthetic loop reset is not physical removal. Actor departure is not automatically measured.',
                    'Repaired or normalized responses cannot satisfy the fresh dispatch gate.'])


def proposal(evidence, created=None):
    runs = evidence['measurements']['qualifying_runs']
    if not runs:
        raise ValueError('No sampled stationary candidate')
    run = runs[0]
    row = next(r for r in evidence['local_cv']['observations'] if r['timestamp_utc'] == run['first'])
    candidates = [o for o in row['objects'] if (o['box'][2]-o['box'][0])*(o['box'][3]-o['box'][1])>=.01]
    obj = max(candidates, key=lambda o:(o['box'][2]-o['box'][0])*(o['box'][3]-o['box'][1]))
    l,t,r,b = obj['box']
    episode = evidence['camera_guid'].lower()+'|'+'|'.join(evidence['interval_utc'])
    capability = camera_config(evidence['camera_name'], evidence['camera_guid'])
    event = capability['event']
    key = dispatch_key(episode, event['policy_id'], event['name'])
    created = created or datetime.now(timezone.utc).isoformat()
    description = ('Potential sidewalk obstruction — review required. '
                   f"Sampled stationarity {run['sampled_span_s']}s; minimum box overlap {run['min_box_overlap']:.1%}. "
                   f"Evidence UTC {run['first']} to {run['last']}. Event created UTC {created}. "
                   'Partial box overlap does not establish clearance. Operator verification required.')
    payload = build(event['name'], evidence['camera_guid'], run['first'], key, description=description,
                    start=evidence['interval_utc'][0], end=evidence['interval_utc'][1],
                    boxes=[dict(left=l,top=t,right=r,bottom=b)], vendor='Adaptive Watch')
    return payload, dict(message=event['name'], dispatch_key=key, xml_sha256=hashlib.sha256(payload).hexdigest(),
                         event_created_utc=created, source_timestamp_utc=run['first'],
                         interval_utc=evidence['interval_utc'], camera_guid=evidence['camera_guid'],
                         box_timestamp_utc=row['timestamp_utc'], box=obj['box'],
                         dispatch_review_ready=evidence.get('dispatch_review_ready',False),
                         automatic_dispatch_eligible=False, event_sent=False)
