"""Re-encode the original XProtect MKV as a browser MP4, frame for frame (no resampling).

Verifies every manifest snapshot against the decoded stream before writing the time map.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adaptive_watch.review_media import prepare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--deps', type=Path, help='directory containing av, numpy, PIL')
    a = p.parse_args()
    info, _ = prepare(a.manifest, a.out, a.deps)
    print(json.dumps(dict(sha256=info['sha256'], frames=info['frames'], maxError=max(x['matchError'] for x in info['samples'][1:]))))


if __name__ == '__main__':
    main()
