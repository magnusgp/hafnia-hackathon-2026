"""Immutable frame-level diagnosis of saved railway predictions; no threshold fitting."""
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from adaptive_watch.tracking import foot, inside
from reliability_plan import sha, read, frozen_write


def audit(root):
    source=REPO/'runs/hybrid/railway-cv-1163ddf.json'
    expected=read(REPO/'results/reliability/saved-analysis.json')['cv_source_sha256']
    if sha(source)!=expected:
        raise ValueError('Original CV prediction bytes changed')
    labels=read(REPO/'runs/reliability-20261026/reviewed-ai-demo.json')['sources'][0]['frames']
    cv=read(source)
    polygon=read(REPO/'docs/research/reliability/railway-geometry-v3.json')['polygon']
    rows=[]
    for i,(obs,label) in enumerate(zip(cv['observations'],labels,strict=True)):
        if obs['timestamp_utc']!=label['timestamp_utc']:
            raise ValueError('Annotation/CV mismatch')
        phase=('platform_approach' if i<4 else 'edge_proximity' if i<6 else
               'seated_edge_proximity' if i<18 else 'visible_descent' if i==18 else
               'confirmed_entry' if i==19 else 'track_occupancy' if i<24 else 'far_platform_exit')
        target_ids={1} if i<5 or i==6 else {1,7,8} if i==5 else {7}
        detections=[]
        for o in obs['objects']:
            if o['track_id'] not in target_ids:
                continue
            x,y=foot(o['box'])
            # Horizontal margin from the unchanged near-platform edge; positive is trackward.
            near_x=.25+(y-.32)*(.62-.25)/(1-.32)
            detections.append(dict(track_id=o['track_id'],box=o['box'],footpoint=[x,y],
                footpoint_px=[x*832,y*480],near_edge_horizontal_margin_px=(x-near_x)*832,
                original_candidate=o['in_zone'],v3_candidate=inside((x,y),polygon)))
        interpretation=('platform_proximity_only' if i<6 else 'seated_proximity_contact_ambiguous' if i<18 else
                        'descent_visible_contact_ambiguous' if i==18 else 'entry_visually_confirmed' if i==19 else
                        'track_presence_visually_confirmed' if i<24 else 'exit_transition_or_platform')
        rows.append(dict(index=i,timestamp_utc=obs['timestamp_utc'],phase=phase,
                         reviewed_label=label['reviewed_label'],detections=detections,
                         review_interpretation=interpretation,
                         automatic_entry_detection='not established by geometry alone'))
    before,after=rows[10]['detections'][0],rows[11]['detections'][0]
    diagnosis=dict(source_sha256=expected,original_predictions_unchanged=True,threshold_changed=False,
        calibration_only=True,reviewed_entry_bracket_utc=['2026-10-22T11:03:48.013Z','2026-10-22T11:03:48.513Z'],
        first_geometric_candidate_utc=rows[11]['timestamp_utc'],candidate_early_seconds=[3.5,4.0],
        boundary_crossing=dict(before=before,after=after,
            footpoint_dx_px=after['footpoint_px'][0]-before['footpoint_px'][0],
            footpoint_dy_px=after['footpoint_px'][1]-before['footpoint_px'][1]),
        cause='Box bottom moves upward while actor remains seated. Bottom-center crosses the perspective near-edge line by only 0.17 horizontal pixels. It is not an anatomical foot/contact estimate.',
        geometry='Original and v3 share near-platform vertices (0.25,0.32) and (0.62,1.0). Changing the far-platform boundary cannot repair this early crossing.',
        tracking='Approach uses track 1; frame 5 contains overlapping hypotheses 1,7,8; seated/crossing uses track 7. All hypotheses retained, no synthetic identity merge.',
        interpretation='Proximity warning and manual-confirmed entry are separate. No automatic posture/contact classifier or independently validated entry rule is claimed.',rows=rows)
    frozen_write(root/'geometry-frame-audit.private.json',diagnosis)
    public={k:v for k,v in diagnosis.items() if k!='rows'}
    public['frames']=[dict(index=r['index'],timestamp_utc=r['timestamp_utc'],phase=r['phase'],
        reviewed_label=r['reviewed_label'],v3_candidates=sum(d['v3_candidate'] for d in r['detections']),
        track_hypotheses=[d['track_id'] for d in r['detections']],review_interpretation=r['review_interpretation']) for r in rows]
    frozen_write(REPO/'results/reliability/railway-frame-audit.json',public)
    print('Audited 26 original frames; first crossing margin %.3f px; no predictions or thresholds changed' % after['near_edge_horizontal_margin_px'])


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if not a.root.resolve().is_relative_to((REPO/'runs').resolve()):p.error('Private output must stay under runs/')
    audit(a.root)
