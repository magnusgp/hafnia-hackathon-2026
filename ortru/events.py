"""Event-level grouping of assessments: which exceptions are the same visual event seen again.

Cameras on these machines replay a short clip, so the same synthetic event is recorded again at every cycle and each
cadence run produces its own assessment, Hafnia answer and exception. Those are kept separately; this module only decides
which of them belong to one event, so a repeat is shown and sent deliberately instead of silently.

Policy (every rule needs its evidence; nothing is hidden, merged away or stopped):
  distinct      different camera, or different Watch focus (condition, detector, parameters, region), is never the same event.
  same occurrence   same focus and the recorded windows overlap in real time: one real moment assessed more than once.
  recurrence    same focus, different times, and BOTH of: identical content (the exported recording has the same hash, or
                the detector tracked the same boxes at every sample) AND the same position in the camera's replay cycle.
  Matching content at a different cycle position, or the same position with different content, stays distinct. With
  no measured cycle position nothing is called a recurrence.
Grouping never changes an assessment, its evidence files, its decision or its native state.
"""
from datetime import datetime

from adaptive_watch.negative_review import digest, read

PHASE_TOLERANCE_S = 0.15   # about one video frame (10 fps)
BOX_TOLERANCE = 0.01       # share of the image, per box coordinate
MIN_BOX_SAMPLES = 3        # a box match with fewer people-bearing samples proves nothing


def _t(iso):
    return datetime.fromisoformat(iso.replace('Z', '+00:00'))


def signature(view, assessment_dir):
    """What identifies an event, from a verified exception view and its job directory."""
    cfg = view['provenance']['watchConfig']
    media = read(assessment_dir/'media/media.json')
    try:
        position = read(assessment_dir/'loop-window.json').get('firstPosition')
    except (OSError, ValueError):
        position = None
    focus = dict(camera=view['camera']['id'].lower(), condition=cfg['hafnia']['condition'], detector=cfg['detector']['id'],
                 parameters=cfg['detector']['parameters'], region=cfg['region'])
    return dict(id=view['id'], focus=digest(focus), start=view['interval'][0], end=view['interval'][1], position=position,
                mkv=media.get('sourceMkvSha256'), boxes=[s['box'] for s in view['vision']['samples']])


def same_content(a, b):
    if a['mkv'] and a['mkv'] == b['mkv']:
        return True
    if len(a['boxes']) != len(b['boxes']) or sum(x is not None for x in a['boxes']) < MIN_BOX_SAMPLES:
        return False
    return all((x is None) == (y is None) and (x is None or all(abs(p-q) <= BOX_TOLERANCE for p, q in zip(x, y)))
               for x, y in zip(a['boxes'], b['boxes']))


def same_phase(a, b):
    return a['position'] is not None and b['position'] is not None and abs(a['position']-b['position']) <= PHASE_TOLERANCE_S


def relation(a, b):
    """'same_occurrence', 'recurrence' or None (distinct)."""
    if a['focus'] != b['focus']:
        return None
    if _t(a['start']) < _t(b['end']) and _t(b['start']) < _t(a['end']):
        return 'same_occurrence'
    if same_content(a, b) and same_phase(a, b):
        return 'recurrence'
    return None


def groups(signatures):
    """Partition signatures into events. Each group: key, members (ids, oldest first), how members relate. Singletons included."""
    sigs = sorted(signatures, key=lambda s: (_t(s['start']), s['id']))
    parent = {s['id']: s['id'] for s in sigs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    links = {}
    for i, a in enumerate(sigs):
        for b in sigs[i+1:]:
            kind = relation(a, b)
            if kind:
                parent[find(b['id'])] = find(a['id'])
                links.setdefault(b['id'], set()).add(kind)
    out = {}
    for s in sigs:
        out.setdefault(find(s['id']), []).append(s)
    result = []
    for members in out.values():
        first = members[0]
        result.append(dict(key='ev-'+digest([first['focus'], first['mkv'] or first['boxes'], first['id'] if first['position'] is None else round(first['position'], 1)])[:12], members=[m['id'] for m in members],
                           relations={m['id']: 'same_occurrence' if 'same_occurrence' in links.get(m['id'], ()) else 'recurrence' for m in members[1:]}))
    return result
