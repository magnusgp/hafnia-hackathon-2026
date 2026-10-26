"""Offline provenance, review draft and saved-result audit. No network or inference."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from adaptive_watch.evaluation import parse_result
from adaptive_watch.tracking import foot, inside


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def prepare(root):
    definitions = REPO / 'docs/reliability/label-definitions.json'
    labels = json.loads(definitions.read_text())
    sources = []
    for scene, directory in [('railway', 'person_on_railway_tracks_20261022T110339Z'),
                             ('gate', 'school_gate_break_in_night_20261022T110438Z')]:
        path = REPO / 'runs/xprotect' / directory / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8-sig'))
        frames = []
        for i, frame in enumerate(manifest['frames']):
            digest = sha(path.parent / frame['file'])
            if frame.get('sha256') and digest != frame['sha256']:
                raise ValueError('Source frame hash mismatch')
            label = 'unreviewed'
            for candidate in ('negative', 'ambiguous', 'positive'):
                if i in labels[scene].get(candidate + '_sample_indices', []):
                    label = candidate
            frames.append(dict(index=i, timestamp_utc=frame['timestamp_utc'],
                               file=str(path.parent / frame['file']), sha256=digest,
                               draft_label=label, reviewer='AI-assisted draft'))
        sources.append(dict(scene=scene, event_id=scene + '-loop-001', manifest=str(path),
                            manifest_sha256=sha(path), frames=frames,
                            video_sha256=sha(path.parent / 'clip.mkv') if (path.parent / 'clip.mkv').exists() else None))
    value = dict(definitions=labels, definitions_sha256=sha(definitions), sources=sources)
    target = root / 'review-draft.json'
    if target.exists() and json.loads(target.read_text()) != value:
        raise ValueError('Existing review differs; preserve it and use a versioned directory')
    save(target, value)
    print('Prepared private review-draft.json; human confirmation pending.')


def analyze(root, responses):
    review = json.loads((root / 'review-draft.json').read_text())
    groups = defaultdict(Counter)
    records = []
    for path in sorted(responses.glob('*.json')):
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or 'request' not in value or 'entry' not in value:
            continue
        entry = value['entry']
        parsed = parse_result(value.get('summary'))
        scene, version = entry['scene'], entry['prompt_version']
        groups[(scene, entry['camera_name'], version)][parsed['category'] + ':' + parsed['outcome']] += 1
        records.append(dict(source_sha256=sha(path), source=str(path), entry=entry,
                            original_request=value['request'], original_summary=value.get('summary'), parsed=parsed))
    save(root / 'saved-response-audit.private.json', records)
    cvpath = REPO / 'runs/hybrid/railway-cv-1163ddf.json'
    cv = json.loads(cvpath.read_text())
    if cv['manifest_sha256'] != review['sources'][0]['manifest_sha256']:
        raise ValueError('CV/source manifest hash mismatch')
    polygon = [[.25,.32],[1,.46],[1,1],[.56,1]]
    results = {}
    for name, corrected in [('original', False), ('revised_calibration_only', True)]:
        rows = []
        for source, obs in zip(review['sources'][0]['frames'], cv['observations'], strict=True):
            if source['timestamp_utc'] != obs['timestamp_utc']:
                raise ValueError('CV/source timestamp mismatch')
            rows.append(dict(index=source['index'], label=source['draft_label'],
                             timestamp_utc=obs['timestamp_utc'],
                             positive=any(inside(foot(o['box']), polygon) if corrected else o['in_zone'] for o in obs['objects']),
                             track_ids=[o['track_id'] for o in obs['objects']]))
        results[name] = dict(counts={label: dict(total=sum(r['label'] == label for r in rows),
            flagged=sum(r['label'] == label and r['positive'] for r in rows))
            for label in ['negative', 'ambiguous', 'positive', 'unreviewed']}, rows=rows)
    save(root / 'cv-audit.private.json', dict(source_sha256=sha(cvpath), results=results,
        status='Retrospective same-clip calibration with AI draft labels; not held-out validation'))
    sanitized = dict(saved_requests=len(records), new_requests=0,
        distributions=[dict(task=k[0], camera=k[1], prompt=k[2], counts=dict(v)) for k,v in sorted(groups.items())],
        cv={k:v['counts'] for k,v in results.items()}, definitions_sha256=review['definitions_sha256'],
        cv_source_sha256=sha(cvpath), independent_events='At most one source loop per scene; no independent failure-rate estimate',
        human_review='pending', hard_negatives='No human-confirmed task-matched negative events evaluated')
    save(REPO / 'results/reliability/saved-analysis.json', sanitized)
    print(json.dumps(sanitized, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'analyze'])
    p.add_argument('--root', type=Path, required=True, help='Ignored private runs directory')
    p.add_argument('--responses', type=Path)
    a = p.parse_args()
    if not a.root.resolve().is_relative_to((REPO / 'runs').resolve()):
        p.error('Output must remain in ignored runs/')
    if a.action == 'prepare':
        prepare(a.root)
    else:
        if not a.responses:
            p.error('--responses required')
        analyze(a.root, a.responses)
