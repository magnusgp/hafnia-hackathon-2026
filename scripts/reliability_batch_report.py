"""Offline audit of the completed four-request batch; never contacts the gateway."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batch = ROOT / 'runs/reliability-fresh/operator-batch'
    plan = json.loads((batch / 'plan.private.json').read_text())
    matrix = json.loads((ROOT / 'docs/reliability/first-batch-matrix.json').read_text())
    expected = {e['experiment_id']: e['body'] + matrix['suffix'] for e in matrix['experiments']}
    db = sqlite3.connect(f'file:{(batch / "reliability-ledger.sqlite3").as_posix()}?mode=ro', uri=True)
    rows = db.execute('select experiment,summary_id,state,payload,result from requests order by experiment').fetchall()
    assert len(rows) == 4 and {r[0] for r in rows} == set(expected)
    results = []
    for experiment, sid, state, payload, result in rows:
        payload, result = json.loads(payload), json.loads(result)
        raw, parsed = result['raw'], result['parsed']
        entry = next(e for e in plan if e['experiment_id'] == experiment)
        assert payload['Prompt'] == expected[experiment] == raw['Request']['Prompt']
        assert payload['VideoUris'] == raw['Request']['VideoUris']
        assert sid == raw['Id'] and raw['Progress'] == 'Completed'
        text = raw['Response'].strip()
        if text.startswith('```json'):
            text = text[len('```json'):].strip()
            assert text.endswith('```')
            text = text[:-3].strip()
        body = json.loads(text)
        assert body['outcome'] == parsed['outcome']
        results.append(dict(experiment_id=experiment, summary_id=sid, gateway_status=raw['Progress'],
            created_at=raw['CreationTimeUtc'], completed_at=raw['LastUpdatedTimeUtc'],
            raw_decision=body['outcome'], parsed_decision=parsed['outcome'], parse_status=state,
            formatting_deviations=parsed.get('normalizations', []), evidence=body['evidence'],
            timing=body['timing'], limitations=body['limitations'],
            prompt=payload['Prompt'], start=entry['start'], end=entry['end'],
            source_sha256=entry['manifest_sha256'],
            raw_response_sha256=hashlib.sha256(raw['Response'].encode()).hexdigest()))
    audit = json.loads((ROOT / 'runs/reliability-20261026/saved-response-audit.private.json').read_text())
    originals = []
    for a in audit:
        assert sha(Path(a['source'])) == a['source_sha256'], 'Original response changed'
        e = a['entry']
        if e['scene'] == e['camera_name'] and e['scene'] in {'person_on_railway_tracks', 'school_gate_break_in_night'}:
            originals.append(dict(scene=e['scene'], prompt_version=e['prompt_version'],
                prompt=a['original_request']['Prompt'], summary_id=a['original_summary']['Id'],
                response_sha256=a['source_sha256'], start=e['start'], end=e['end'], parsed=a['parsed']))
    output = dict(batch_id='REL26-B-first4', actual_requests=4, distinct_source_loop_families=2,
                  independent_new_events=0, original_response_files_verified=16,
                  results=results, original_comparison=originals,
                  limitations=['Authorized AI demo reference review, not human attestation',
                               'Gateway internal decoded/model-consumed frames unavailable',
                               'Fresh loop recordings differ from historical sources; not a paired prompt-only experiment',
                               'No eligible task-matched hard-negative events',
                               'No validated failure rate from these correlated requests'])
    target = ROOT / 'results/reliability/completed-first-four.json'
    target.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print('Verified four completed requests, exact prompts/URIs, and 16 unchanged original response files')


if __name__ == '__main__':
    main()
