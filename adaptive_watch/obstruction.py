"""Conservative image-space persistence from saved object detections.

Rules are fixed technical demo defaults, not calibrated incident thresholds.
No interpolation, person association, object-mask claim, or event dispatch.
"""
from datetime import datetime
from math import hypot


def seconds(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('Offset required')
    return d.timestamp()


def center(box):
    return ((box[0]+box[2])/2, (box[1]+box[3])/2)


def distance(a, b):
    return hypot(a[0]-b[0], a[1]-b[1])


def measure(observations, *, tolerance=0.025, min_duration=3.0, max_gap=1.5):
    """Largest >=1% image-area target, >=10% box overlap, bounded anchor drift.

    Largest-object selection is a foreground hypothesis, not general tracking.
    A review candidate additionally needs >=5% image-coordinate displacement
    from the first localized center; an already static edge bin cannot qualify.
    """
    trajectory, runs, current, initial = [], [], [], None

    def finish():
        if not current:
            return
        duration = seconds(current[-1]['timestamp_utc'])-seconds(current[0]['timestamp_utc'])
        runs.append(dict(first=current[0]['timestamp_utc'],last=current[-1]['timestamp_utc'],
            sampled_span_s=duration,samples=len(current),
            max_anchor_drift=max(distance(x['center'],current[0]['center']) for x in current),
            moved_from_initial=distance(current[0]['center'],initial)>=0.05,
            min_box_overlap=min(x['box_walkway_overlap'] for x in current)))

    for row in observations:
        candidates = [o for o in row['objects'] if
                      (o['box'][2]-o['box'][0])*(o['box'][3]-o['box'][1])>=0.01]
        o = max(candidates,key=lambda o:(o['box'][2]-o['box'][0])*(o['box'][3]-o['box'][1]),default=None)
        point = dict(timestamp_utc=row['timestamp_utc'],object=o,
                     center=None if o is None else center(o['box']))
        trajectory.append(point)
        if o is None or o['box_walkway_overlap']<0.1:
            finish()
            current = []
            continue
        if initial is None:
            initial = point['center']
        point['box_walkway_overlap'] = o['box_walkway_overlap']
        if current and (seconds(point['timestamp_utc'])-seconds(current[-1]['timestamp_utc'])>max_gap
                        or distance(point['center'], current[0]['center'])>tolerance):
            finish()
            current=[]
        current.append(point)
    finish()
    qualifying = [r for r in runs if r['sampled_span_s']>=min_duration and r['moved_from_initial']]
    return dict(trajectory=trajectory,stationary_runs=runs,qualifying_runs=qualifying,
        candidate=bool(qualifying),thresholds=dict(anchor_drift=tolerance,min_duration_s=min_duration,
            max_gap_s=max_gap,min_area=0.01,min_box_overlap=0.1,min_displacement=0.05),
        limitations=['Foreground largest-box hypothesis can switch targets; inspect overlay.',
            'Three-second demo threshold does not establish operationally significant obstruction.',
            'Stationary means bounded sampled image-center drift; no claim between samples.',
            'Displacement requirement cannot detect an obstruction already present at clip start.'])
