"""Verify frozen private evidence and materialize the first four requests OFFLINE.

No gateway access, authentication, inference, video editing or native dispatch.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from adaptive_watch.evaluation import prompt
from scene_contracts.gateway import video_uri


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def frozen_write(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Frozen artifact differs: ' + path.name)
        return
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def prepare(root, responses):
    signoff = read(root / 'review-signoff.json')
    artifact = Path(signoff['review_artifact'])
    if sha(artifact) != signoff['review_artifact_sha256']:
        raise ValueError('Frozen review hash mismatch')
    review = read(artifact)
    definitions = REPO / 'docs/reliability/label-definitions.json'
    if sha(definitions) != signoff['definitions_sha256'] or sha(definitions) != review['definitions_sha256']:
        raise ValueError('Frozen definition hash mismatch')
    sources = {}
    frame_counts = {}
    for source in review['sources']:
        manifest = Path(source['manifest'])
        if sha(manifest) != source['manifest_sha256']:
            raise ValueError('Manifest changed')
        m = read(manifest)
        if len(m['frames']) != len(source['frames']):
            raise ValueError('Review frame coverage differs')
        previous = None
        for label, frame in zip(source['frames'], m['frames'], strict=True):
            file = (manifest.parent / frame['file']).resolve()
            if not file.is_relative_to(manifest.parent.resolve()) or sha(file) != label['sha256']:
                raise ValueError('Reviewed frame changed')
            timestamp = datetime.fromisoformat(frame['timestamp_utc'].replace('Z', '+00:00'))
            if frame['timestamp_utc'] != label['timestamp_utc'] or previous and timestamp <= previous:
                raise ValueError('Frame timestamp mismatch or nonmonotonic sequence')
            if label['reviewed_label'] not in {'positive','negative','ambiguous'}:
                raise ValueError('Incomplete reference annotation')
            previous = timestamp
        if source.get('video_sha256') and sha(manifest.parent / 'clip.mkv') != source['video_sha256']:
            raise ValueError('Original video changed')
        sources[source['event_id']] = source
        frame_counts[source['event_id']] = dict(Counter(f['reviewed_label'] for f in source['frames']))
    saved = []
    summaries = set()
    original_locks = []
    audit = {str(Path(v['source']).resolve()).casefold():v['source_sha256']
             for v in read(root / 'saved-response-audit.private.json')}
    for path in sorted(responses.glob('*.json')):
        value = read(path)
        if not isinstance(value, dict) or 'request' not in value or 'entry' not in value:
            continue
        entry = value['entry']
        raw_sha = sha(path)
        if audit.get(str(path.resolve()).casefold()) != raw_sha:
            raise ValueError('Original response bytes differ from saved provenance audit')
        start, end = [datetime.fromisoformat(entry[k].replace('Z','+00:00')) for k in ('start','end')]
        expected = dict(Prompt=prompt(entry['scene'],entry['prompt_version']),
                        VideoUris=[video_uri(entry['camera_id'],start,end)])
        digest = hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest()
        if value['request'] != expected or value['request_sha256'] != digest:
            raise ValueError('Saved request does not match original prompt/interval/hash')
        summary_id = value['summary']['Id']
        if summary_id in summaries:
            raise ValueError('Duplicate saved summary; do not count twice')
        summaries.add(summary_id)
        original_locks.append(dict(file=str(path.resolve()),sha256=raw_sha,summary_id=summary_id))
        saved.append(value)
    if len(saved) != 16:
        raise ValueError('Expected the original 16 saved assessments')
    frozen_write(root / 'original-response-hashes.private.json', original_locks)
    matrix_path = REPO / 'docs/reliability/first-batch-matrix.json'
    matrix = read(matrix_path)
    plan = []
    for spec in matrix['experiments']:
        old = next(v for v in saved if v['entry']['scene'] == spec['scene']
                   and v['entry']['camera_name'] == spec['scene'] and v['entry']['prompt_version'] == 'v1')
        entry = old['entry']
        source = sources[spec['event_id']]
        # Exact old interval: no implicit reacquisition or source substitution.
        if spec['event_id'] == 'gate-loop-001':
            reset_start = source['frames'][14]['timestamp_utc']
            if datetime.fromisoformat(entry['end'].replace('Z','+00:00')) >= datetime.fromisoformat(reset_start.replace('Z','+00:00')):
                raise ValueError('Gate interval overlaps reset uncertainty')
        plan.append(dict(experiment_id=spec['experiment_id'],stage='B',event_id=spec['event_id'],
            scene=spec['scene'],prompt_version=spec['prompt_version'],prompt=spec['body']+matrix['suffix'],
            camera_id=entry['camera_id'],start=entry['start'],end=entry['end'],
            recording_manifest=source['manifest'],manifest_sha256=source['manifest_sha256'],
            label_review_sha256=signoff['review_artifact_sha256'],continuity_review='ai_reviewed_no_loop_boundary',
            continuity_scope='Sampled-frame review; unsampled full-motion continuity unverified',
            matrix_sha256=sha(matrix_path)))
    if len(plan) != matrix['expected_new_requests']:
        raise ValueError('Matrix count mismatch')
    frozen_write(root / 'first-batch.private.json',plan)
    summary = dict(batch_id=matrix['batch_id'],expected_new_requests=len(plan),
        saved_requests_verified=len(saved),reviewed_frame_counts=frame_counts,
        review_artifact_sha256=sha(artifact),matrix_sha256=sha(matrix_path),
        intervals=[dict(experiment_id=e['experiment_id'],event_id=e['event_id'],start=e['start'],end=e['end']) for e in plan],
        status='Offline verified; no authentication or submissions performed',
        source_availability='Not verified; original October 22 recordings may have expired',
        negative_controls=matrix['negative_control_policy'])
    frozen_write(root / 'first-batch-verification.json',summary)
    frozen_write(REPO / 'results/reliability/first-batch-readiness.json',summary)
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--responses',type=Path,required=True)
    a=p.parse_args()
    if not a.root.resolve().is_relative_to((REPO/'runs').resolve()):
        p.error('Private plans must stay in ignored runs/')
    prepare(a.root,a.responses)
