"""Render private detector evidence and summarize the baseline on Linux."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('report',type=Path)
p.add_argument('recording',type=Path)
a = p.parse_args()
r = json.loads(a.report.read_text())
frames = r['source_manifest']['frames']
sheet = Image.new('RGB',(4*416,((len(frames)+3)//4)*260))
for i,(f,obs) in enumerate(zip(frames,r['observations'])):
    with Image.open(a.recording/f['file']) as src:
        im = src.convert('RGB').resize((416,240))
    draw = ImageDraw.Draw(im)
    draw.polygon([(x*416,y*240) for x,y in r['zone']['polygon']],outline='yellow',width=2)
    for obj in obs['objects']:
        b=obj['box']
        color='red' if obj['in_zone'] else 'lime'
        draw.rectangle((b[0]*416,b[1]*240,b[2]*416,b[3]*240),outline=color,width=2)
        draw.text((b[0]*416,b[1]*240),str(obj['track_id']),fill=color)
    x,y=i%4*416,i//4*260
    sheet.paste(im,(x,y))
    ImageDraw.Draw(sheet).text((x,y+240),f['timestamp_utc'],fill='white')
sheet.save(a.report.with_suffix('.jpg'))
rows=[]
for obs,base in zip(r['observations'],r['motion_baseline']):
    if base['changed_zone_fraction'] is not None:
        rows.append((any(o['in_zone'] for o in obs['objects']),base['changed_zone_fraction']))
print(json.dumps(dict(
    frames_with_person_in_zone=sum(x for x,y in rows),
    motion_baseline_ms_per_frame=1000*np.mean([x['elapsed_s'] for x in r['motion_baseline']]),
    zone_person_motion_range=[min(y for x,y in rows if x),max(y for x,y in rows if x)],
    no_zone_person_motion_range=[min(y for x,y in rows if not x),max(y for x,y in rows if not x)],
    at_fixed_1pct_change_threshold=dict(
        motion_positive_with_zone_person=sum(x and y>0.01 for x,y in rows),
        motion_positive_without_zone_person=sum(not x and y>0.01 for x,y in rows),
        motion_negative_with_zone_person=sum(x and y<=0.01 for x,y in rows)),
    interpretation='Agreement with detector observations only, not ground-truth accuracy.'),indent=2))
