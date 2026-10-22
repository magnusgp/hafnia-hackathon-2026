"""Offline-only, append-only recovery. Never opens a gateway or writes the ledger."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adaptive_watch.evaluation import parse_result, PARSER_VERSION


def recover(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError('Output must be separate from original evidence')
    files = sorted(root.glob('*.json'))
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
    aggregate = json.loads((root/'aggregate.json').read_text())
    classifications = {r['digest']: r for r in aggregate['requests']}
    db = sqlite3.connect((root/'ledger.sqlite3').as_uri()+'?mode=ro', uri=True)
    ledger = {d: (sid, state, json.loads(record)) for d, sid, state, record in db.execute(
        'SELECT digest,summary_id,state,record FROM submissions')}
    db.close()
    rows = []
    for path in files:
        if path.name == 'aggregate.json':
            continue
        r = json.loads(path.read_text())
        s = r['summary']; raw = s.get('Response')
        sid, state, claim = ledger[path.stem]
        if sid != s['Id'] or claim['request_sha256'] != path.stem or claim['request'] != r['request']:
            raise ValueError('Ledger provenance mismatch')
        rows.append(dict(digest=path.stem, scene=r['entry']['scene'], prompt_version=r['entry']['prompt_version'],
            control=r['entry']['camera_name']=='busy_street', summary_id=sid, gateway_status=s.get('Progress'),
            ledger_state=state, response_exists='Response' in s, response_type=type(raw).__name__,
            response_length=len(raw) if isinstance(raw, (str,list,dict)) else None,
            original_parse_error='JSONDecodeError: Expecting value: line 1 column 1 (char 0); opening Markdown fence',
            original_classification=classifications[path.stem], original_parsed=r.get('parsed'),
            corrected=parse_result(s), source_sha256=originals[path.name]))
    report = dict(parser_version=PARSER_VERSION, offline=True, original_hashes=originals, requests=rows,
                  counts=dict(Counter(r['corrected']['category'] for r in rows)))
    output.mkdir(parents=True, exist_ok=False)
    for path in root.iterdir():
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != originals[path.name]:
            raise ValueError('Original evidence changed')
    (output/'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for r in rows:
        print(r['digest'][:10], r['scene'], r['prompt_version'], 'control' if r['control'] else '',
              r['gateway_status'], r['response_type'], r['response_length'], r['corrected']['outcome'],
              ','.join(r['corrected'].get('normalizations', [])))
    print(json.dumps(report['counts']))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    recover(a.root, a.output)
