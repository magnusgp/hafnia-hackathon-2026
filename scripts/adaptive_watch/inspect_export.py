"""Audit MKV timestamps without inventing a requested end or asserting absolute PTS origin."""
import argparse
import hashlib
import json
from pathlib import Path
import av

p=argparse.ArgumentParser()
p.add_argument('manifest',type=Path)
p.add_argument('mkv',type=Path)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
m=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
pts=[]
with av.open(str(a.mkv)) as c:
    s=c.streams.video[0]
    for f in c.decode(s):
        if f.pts is None:
            raise ValueError('Missing frame PTS')
        pts.append(float(f.pts*s.time_base))
r=dict(camera_id=m['camera_id'],requested_start_utc=m['requested_start_utc'],
       requested_end_utc=m['requested_end_utc'],decoded_frames=len(pts),first_pts_s=pts[0],last_pts_s=pts[-1],
       decoded_pts_span_s=pts[-1]-pts[0],mkv_sha256=hashlib.sha256(a.mkv.read_bytes()).hexdigest(),
       absolute_time_status='Unverified: PTS alone does not establish first-frame UTC. CV uses server-timestamped JPEGs instead.')
a.out.write_text(json.dumps(r,indent=2))
print(json.dumps(r,indent=2))
