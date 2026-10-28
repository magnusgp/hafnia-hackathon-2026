"""Re-score saved detections only; same-clip geometry calibration, no ML run."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adaptive_watch.tracking import foot, inside
r=Path('runs/hybrid')
data=json.loads((r/'railway-cv-1163ddf.json').read_text())
polygon=[[.25,.32],[1,.46],[1,1],[.56,1]]
# Broad track-bed image region. Sitting/occlusion requires semantic review.
rows=[]
for obs in data['observations']:
    rows.append(dict(timestamp_utc=obs['timestamp_utc'],objects=[dict(o, corrected_footpoint=foot(o['box']),corrected_in_zone=inside(foot(o['box']),polygon),entry_status='geometric_candidate_only_requires_visible_track_bed_contact') for o in obs['objects']]))
result=dict(source='railway-cv-1163ddf.json',polygon=polygon,observations=rows,entry_rule='Polygon crossing is only a review candidate. Establish descent and foot/body contact with track bed visually; sitting on edge is uncertain. Never dispatch from membership alone.',keyframes=[dict(index=i,observation=s) for i,s in [(2,'Before descent: standing on platform'),(7,'At boundary: seated, legs over edge; physical occupancy uncertain'),(18,'Descent transition; contact partly occluded'),(19,'First sampled clearly established standing entry in track bed'),(21,'Remains in track bed')]],metrics=dict(visually_established_entry_utc='2026-10-22T11:03:48.513Z',entry_bracket_utc=['2026-10-22T11:03:48.013Z','2026-10-22T11:03:48.513Z'],original_proxy_onset_utc='2026-10-22T11:03:44.513Z',original_onset_error_s=[-4.0,-3.5],missed_occupancy='Not exhaustively labelled; cannot estimate rate',false_occupancy='Original positive membership precedes clearly established entry by 3.5–4 seconds; seated interval uncertain, not proven false',corrected_accuracy='Unmeasured; same frames used for calibration, no independent validation'),limitations=['Contact sheet only; pixel boundary and anatomical feet uncertain.','Track IDs are association hypotheses.','These frames are calibration observations, never held-out validation.'])
(r/'railway-geometry-review.json').write_text(json.dumps(result,indent=2))
svg=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="832" height="1450" viewBox="0 0 832 1450">','<rect width="100%" height="100%" fill="#111"/>']
for n,k in enumerate(result['keyframes']):
    i=k['index']; y=n*286
    svg.append(f'<svg x="0" y="{y}" width="416" height="240" viewBox="{(i%4)*416} {(i//4)*260} 416 240"><image width="1664" height="1820" href="railway-cv-1163ddf.jpg"/></svg>')
    # Contact sheet pixels are 416x240 per frame; add revised geometry in cyan.
    pts=' '.join(f'{x*416},{yy*240+y}' for x,yy in polygon)
    svg.append(f'<polygon points="{pts}" fill="none" stroke="cyan" stroke-width="2"/>')
    svg.append(f'<text x="420" y="{y+25}" fill="white" font-size="12">{k["observation"]}</text>')
    svg.append(f'<text x="0" y="{y+260}" fill="white">{rows[i]["timestamp_utc"]} — calibration only; cyan revised proxy</text>')
svg.append('</svg>')
(r/'railway-geometry-review.svg').write_text('\n'.join(svg),encoding='utf-8')
