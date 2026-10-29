"""Verified CV capability registry. A Watch can only use a capability that is listed here and available.

This is not a prompt-to-detector generator: each entry names a real runner, the parameters it accepts and what its
output can and cannot establish.
"""

CAPABILITIES = {
    'person_region_proximity': dict(
        id='person_region_proximity', label='Person near a region', available=True,
        runner='scripts/adaptive_watch/railway_cv.py', model='fasterrcnn_resnet50_fpn_v2 (COCO person) on the Linux A10G',
        needsRegion=True, samplesPerSecond=2,
        parameters=dict(margin=dict(type='number', default=0, min=0, max=0.2,
                                    label='Also counts when the person\'s foot is this close to the region (share of the image width)')),
        establishes='A tracked person\'s foot was inside or near the drawn region at a sampled moment. This is proximity, not entry.',
        cannot='Does not confirm that a person entered or stayed; detections can be missed and identities can switch.'),
    'object_stationarity': dict(
        id='object_stationarity', label='Object left in place', available=False,
        reason='Needs the object-localization model and a stationarity runner that has not been made operational on the A10G for this release.',
        needsRegion=True, parameters={}, establishes='', cannot=''),
}

HAFNIA_OUTCOMES = ('observed', 'not_observed', 'uncertain')


def listing():
    return [dict(c) for c in CAPABILITIES.values()]


def validate_region(region):
    if not isinstance(region, dict) or not isinstance(region.get('polygon'), list):
        raise ValueError('The region needs a polygon')
    pts = region['polygon']
    if not 3 <= len(pts) <= 12:
        raise ValueError('A region needs between 3 and 12 points')
    out = []
    for p in pts:
        if (not isinstance(p, (list, tuple)) or len(p) != 2 or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in p)):
            raise ValueError('Region points must be normalized (0 to 1) x, y pairs')
        out.append([round(float(p[0]), 4), round(float(p[1]), 4)])
    area = abs(sum(out[i][0]*out[(i+1) % len(out)][1]-out[(i+1) % len(out)][0]*out[i][1] for i in range(len(out))))/2
    if area < 0.002:
        raise ValueError('The region is too small to draw meaningfully')
    return dict(polygon=out)


def check_detector(detector, region):
    """Returns (detectorId, parameters, region) normalized, or raises ValueError with the operator-facing reason."""
    if not isinstance(detector, dict):
        raise ValueError('Choose what local vision should watch')
    cap = CAPABILITIES.get(detector.get('id'))
    if cap is None:
        raise ValueError(f"Unknown detector '{detector.get('id')}'")
    if not cap['available']:
        raise ValueError(f"{cap['label']} is not available: {cap['reason']}")
    params = {}
    for key, spec in cap['parameters'].items():
        value = (detector.get('parameters') or {}).get(key, spec['default'])
        if type(value) not in (int, float) or not spec['min'] <= value <= spec['max']:
            raise ValueError(f"{key} must be a number from {spec['min']} to {spec['max']}")
        params[key] = value
    unknown = set(detector.get('parameters') or {}) - set(cap['parameters'])
    if unknown:
        raise ValueError('Unknown detector parameter: '+', '.join(sorted(unknown)))
    if cap['needsRegion']:
        region = validate_region(region)
    return dict(id=cap['id'], parameters=params), region
