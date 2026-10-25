"""Small explicit camera registry. Draft geometry never grants operational approval."""
import json
import math
from pathlib import Path
from uuid import UUID

DEFAULT = Path(__file__).resolve().parents[1] / 'config/camera-capabilities.json'


def cameras(path=DEFAULT):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data['schema_version'] != 1:
        raise ValueError('Unsupported capability configuration')
    names, ids = set(), set()
    for c in data['cameras']:
        guid = str(UUID(c['camera_guid']))
        if c['name'] in names or guid in ids:
            raise ValueError('Duplicate camera configuration')
        names.add(c['name']); ids.add(guid)
        if c['capability'] != 'persistent_object' or not c['queries'] or any(not isinstance(q,str) or not q.strip() for q in c['queries']):
            raise ValueError('Unsupported capability or object queries')
        policy = c['temporal_policy']
        if set(policy) != {'tolerance','min_duration','max_gap'} or any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in policy.values()):
            raise ValueError('Invalid temporal policy')
        if c['region'].get('approved') is not False:
            raise ValueError('Registry regions are drafts; use camera-specific spatial approval')
        if not c['event']['name'] or not c['event']['policy_id']:
            raise ValueError('Event identity required')
        c['camera_guid'] = guid
    return data['cameras']


def camera_config(name=None, guid=None, path=DEFAULT):
    matches = [c for c in cameras(path) if (name is None or c['name'] == name) and
               (guid is None or c['camera_guid'] == guid.lower())]
    if len(matches) != 1:
        raise ValueError('Camera capability mapping missing or mismatched')
    return matches[0]
