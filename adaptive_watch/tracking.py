"""Small, deterministic image-space tracker and zone measurements (no incident claim)."""
from math import hypot


def inside(point, polygon):
    x, y = point
    odd = False
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            odd = not odd
    return odd


def foot(box):
    return ((box[0]+box[2])/2, box[3])


class Tracker:
    """Greedy nearest-foot association. IDs are hypotheses, never verified identities."""
    def __init__(self, max_distance=0.22, max_gap_s=1.1):
        self.max_distance, self.max_gap_s = max_distance, max_gap_s
        self.tracks = {}
        self.next_id = 1

    def update(self, t, detections, polygon):
        pairs = sorted((hypot(*(a-b for a,b in zip(foot(d['box']), foot(v[-1]['box'])))), k, i)
                       for k,v in self.tracks.items() if 0 < t-v[-1]['t'] <= self.max_gap_s
                       for i,d in enumerate(detections))
        matched, used = {}, set()
        for distance, k, i in pairs:
            if distance <= self.max_distance and i not in matched and k not in used:
                matched[i] = k
                used.add(k)
        observations = []
        for i,d in enumerate(detections):
            k = matched.get(i)
            if k is None:
                k, self.next_id = self.next_id, self.next_id+1
                self.tracks[k] = []
            row = dict(d, track_id=k, t=t, in_zone=inside(foot(d['box']), polygon))
            self.tracks[k].append(row)
            observations.append(row)
        return observations

    def measurements(self):
        result = []
        for k, rows in self.tracks.items():
            pairs = list(zip(rows, rows[1:]))
            confirmed = [(a,b) for a,b in pairs if b['t']-a['t'] <= self.max_gap_s]
            result.append(dict(track_id=k, observations=len(rows), first_t=rows[0]['t'], last_t=rows[-1]['t'],
                observed_zone_s=sum(b['t']-a['t'] for a,b in confirmed if a['in_zone'] and b['in_zone']),
                zone_entry_brackets_s=[[a['t'],b['t']] for a,b in confirmed if not a['in_zone'] and b['in_zone']],
                normalized_path_length=sum(hypot(*(x-y for x,y in zip(foot(a['box']),foot(b['box'])))) for a,b in confirmed),
                min_detection_score=min(r['score'] for r in rows)))
        return result
