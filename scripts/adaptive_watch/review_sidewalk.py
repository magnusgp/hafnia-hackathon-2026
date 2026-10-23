"""Build a private, offline frame player and operator geometry review images.

Uses original hash-verified frames; never submits inference or native events.
"""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def export(evidence, manifest, out, proposal_dir=None):
    e = json.loads(evidence.read_text())
    cv = e['local_cv']
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != e['manifest_sha256']:
        raise ValueError('Acquisition manifest hash mismatch')
    m = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if m != cv['source_manifest'] or m['camera_id'].lower() != e['camera_guid'].lower():
        raise ValueError('Camera or manifest mismatch')
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for n, row in enumerate(cv['observations']):
        source = (manifest.parent / row['file']).resolve()
        if not source.is_relative_to(manifest.parent.resolve()):
            raise ValueError('Frame outside acquisition directory')
        if hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Frame hash mismatch')
        name = f'frame-{n:04d}.jpg'
        shutil.copyfile(source, out / name)
        frames.append(dict(row, file=name))
    run = next(iter(e['measurements']['qualifying_runs']), None)
    index = next((i for i, r in enumerate(frames) if run and r['timestamp_utc'] == run['first']), 0)
    row = frames[index]
    uri = 'data:image/jpeg;base64,' + base64.b64encode((out/row['file']).read_bytes()).decode()
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="800" viewBox="0 0 1920 800">',
           '<rect width="1920" height="800" fill="#101b26"/>',
           f'<image href="{uri}" x="0" y="55" width="960" height="540" preserveAspectRatio="none"/>',
           f'<image href="{uri}" x="960" y="55" width="960" height="540" preserveAspectRatio="none"/>']
    points = ' '.join(f'{960+x*960},{55+y*540}' for x,y in cv['scene']['walkway'])
    svg.append(f'<polygon points="{points}" fill="none" stroke="cyan" stroke-width="4"/>')
    for obj in row['objects']:
        if (obj['box'][2]-obj['box'][0])*(obj['box'][3]-obj['box'][1]) < .01:
            continue
        l,t,r,b = obj['box']
        svg.append(f'<rect x="{960+l*960}" y="{55+t*540}" width="{(r-l)*960}" height="{(b-t)*540}" fill="none" stroke="lime" stroke-width="4"/>')
    approved = e.get('spatial',{}).get('approved') is True
    lines = [f"{e['camera_name']} | {e['camera_guid']} | {row['timestamp_utc']}",
             'Original frame (left) | Draft pedestrian polygon cyan, detected boxes green (right)',
             f"Sampled stationarity: {run['first']} to {run['last']} = {run['sampled_span_s']} s" if run else 'No qualifying sampled stationarity',
             f"Minimum box overlap: {run['min_box_overlap']:.1%}; box overlap does not measure usable sidewalk clearance." if run else '',
             ('OPERATOR-APPROVED ZONE. ' if approved else 'APPROVAL OUTSTANDING. ')+'Same-clip calibration; scores are not calibrated confidence.',
             'Review curb/bike-lane boundary and wall occlusion. No physical removal inferred at a synthetic loop reset.']
    for i, line in enumerate(lines):
        svg.append(f'<text x="20" y="{30 if i == 0 else 625+(i-1)*30}" fill="white" font-family="sans-serif" font-size="20">{html.escape(line)}</text>')
    svg.append('</svg>')
    (out/'polygon-review.svg').write_text('\n'.join(svg), encoding='utf-8')
    config = dict(schema_version=1, camera_guid=e['camera_guid'], camera_name=e['camera_name'],
                  polygon=cv['scene']['walkway'], approved=approved, approved_by=None, approved_at=None,
                  calibration='same saved clips; not independently validated',
                  reference_frame_sha256=row['sha256'], correction_required=(
                      'Review pavement boundary; diagonal excludes part of scooter.' if 'scooter' in e['camera_name']
                      else 'Review usable pedestrian area and wall-side occlusion for this bin camera.'))
    config = e.get('spatial',config)
    (out/'spatial.local.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    annotations = None
    manual = evidence.parent/'manual-review.json'
    if manual.exists():
        annotations = json.loads(manual.read_text())['scenes'].get('scooter' if 'scooter' in e['camera_name'] else 'bin')
    event = None
    proposal_dir = proposal_dir or evidence.parent
    if (proposal_dir/'proposal.json').exists() and (proposal_dir/'proposal.xml').exists():
        event = json.loads((proposal_dir/'proposal.json').read_text())
        if sha_xml := event.get('xml_sha256'):
            if hashlib.sha256((proposal_dir/'proposal.xml').read_bytes()).hexdigest() != sha_xml:
                raise ValueError('XML preview hash mismatch')
        shutil.copyfile(proposal_dir/'proposal.xml', out/'proposal.xml')
    data = dict(camera=e['camera_name'], interval=e['interval_utc'], frames=frames,
                polygon=config['polygon'], approved=approved, runs=e['measurements']['qualifying_runs'],
                annotations=annotations, event=event,
                hafnia=e['hafnia'], agreement=e.get('agreement', 'Unassessed'),
                decision=e['proposed_operator_decision'], limitations=e['limitations'])
    template = (Path(__file__).parents[2]/'adaptive_watch'/'review.html').read_text(encoding='utf-8')
    # Escape script delimiters in private model text.
    template = template.replace('__EVIDENCE__', json.dumps(data).replace('<', '\\u003c'))
    (out/'index.html').write_text(template, encoding='utf-8')
    print(out.resolve()/'index.html')


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('evidence', type=Path)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--proposal', type=Path, help='Optional exact XML proposal directory')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if a.out.resolve().is_relative_to(repo) and not a.out.resolve().is_relative_to(repo/'runs'):
        p.error('Private viewer output must be under ignored runs/ or outside repository')
    export(a.evidence, a.manifest, a.out, a.proposal)


if __name__ == '__main__':
    main()
