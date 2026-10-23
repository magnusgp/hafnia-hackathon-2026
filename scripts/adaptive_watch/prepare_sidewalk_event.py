"""Prepare private native-event proposal bytes; no definition or dispatch APIs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adaptive_watch.incident import proposal as make_proposal


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('evidence',type=Path)
    p.add_argument('--camera-map',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    e=json.loads(a.evidence.read_text())
    cameras=json.loads(a.camera_map.read_text(encoding='utf-8-sig'))
    matches=[c for c in cameras if c['Name']==e['camera_name']]
    if len(matches)!=1 or matches[0]['Id'].lower()!=e['camera_guid'].lower():
        raise ValueError('Exact unique camera mapping required')
    runs=e['measurements']['qualifying_runs']
    if not runs:
        raise ValueError('No measured review candidate')
    payload, event_metadata = make_proposal(e)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'proposal.xml').write_bytes(payload)
    proposal=dict(**event_metadata,camera=matches[0],
        evidence_sha256=hashlib.sha256(a.evidence.read_bytes()).hexdigest(),
        definition_created=False,
        approval_required=['Walkway polygon and observed object overlap',
            'Distinct Analytics Event definition and camera-scoped alarm definition',
            'Operator-reviewed incident eligibility despite retrospective malformed response',
            'Separate approval of exact XML SHA-256 immediately before any send'],
        workflow=['Review native recorded video for the exact interval and private CV overlays.',
            'Confirm object lies in usable walkway; dismiss partial overlap if not obstructing.',
            'Approve and create exact named event and camera-scoped alarm only after explicit authorization.',
            'Rebuild preview after any change; approve SHA-256, claim persistent SQLite dispatch row before POST.',
            'Use existing dispatch tracking and duplicate suppression; no automatic retry.',
            'Reconcile uncertain outcomes; verify actual camera/event/native alarm in Smart Client.'],
        )
    (a.out/'proposal.json').write_text(json.dumps(proposal,indent=2))
    print('Prepared private proposal only; SHA-256',proposal['xml_sha256'])


if __name__=='__main__':
    main()
