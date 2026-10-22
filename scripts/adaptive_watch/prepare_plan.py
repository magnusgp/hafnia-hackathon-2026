"""Expand PRIVATE, manually reviewed recording selections into an evaluation plan.

Selection JSON: list of {scene, recording_manifest, start, end,
continuity_review: "no_loop_boundary", continuity_review_basis, prompt_versions: ["v1", "v2"]}.
Use one version for controls. Dates must come from actual recent recordings.
No request is sent by this script.
"""
import argparse
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('selections',type=Path)
p.add_argument('--out',type=Path,default=Path('runs/hybrid/plan.json'))
a=p.parse_args()
entries=[]
for selection in json.loads(a.selections.read_text(encoding='utf-8-sig')):
    path=Path(selection['recording_manifest'])
    m=json.loads(path.read_text(encoding='utf-8-sig'))
    for version in selection.get('prompt_versions',['v1','v2']):
        entries.append(dict(scene=selection['scene'],camera_name=m['camera_name'],camera_id=m['camera_id'],
            start=selection['start'],end=selection['end'],prompt_version=version,recording_manifest=str(path),
            continuity_review=selection['continuity_review'],continuity_review_basis=selection['continuity_review_basis']))
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.write_text(json.dumps(entries,indent=2))
print(f'{len(entries)} planned requests; none submitted')
