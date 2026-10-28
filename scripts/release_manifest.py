"""Write the release manifest: build, commit, evidence hashes, video and verification results.

Re-verifies every saved case's source integrity first. Contains hashes and statuses only, no private paths or media.

  python scripts/release_manifest.py --evaluations <dir> --video <mp4> --tests "201 passed, 17 skipped" --checks "all 60 checks passed"
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'runs/tooling/pydeps'))
from adaptive_watch.casebook import Casebook
from adaptive_watch.negative_review import ReviewStore, read


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evaluations', type=Path, required=True)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--tests', required=True)
    p.add_argument('--checks', required=True)
    p.add_argument('--out', type=Path, default=ROOT/'docs/submission/release-manifest.json')
    a = p.parse_args()
    import av
    with av.open(str(a.video)) as c:
        duration = float(c.duration/av.time_base)
        stream = c.streams.video[0]
        size = (stream.width, stream.height)
    if not 0 < duration < 180:
        raise SystemExit(f'Video duration {duration:.1f}s is not under 180 s')
    book = Casebook(ROOT, ROOT/'runs/release/app', ROOT/'runs/negative-result-review', a.evaluations, ROOT/'runs/release')
    try:
        index = book.index()
        if index['unavailable']:
            raise SystemExit(f"Source verification failed: {index['unavailable']}")
        railway = book.view('railway')
    finally:
        book.close()
    store = ReviewStore(ROOT/'runs/negative-result-review')
    try:
        store.verified()  # raises if any original source hash changed
    finally:
        store.close()
    dist = ROOT/'frontend/dist'
    native = read(ROOT/'runs/release/native/status.json')['railway']
    manifest = dict(
        product='Adaptive Watch', branch=git('rev-parse', '--abbrev-ref', 'HEAD'), commit=git('rev-parse', 'HEAD'),
        workingTreeClean=git('status', '--porcelain') == '',
        app=dict(entry='frontend/dist/index.html', entrySha256=sha(dist/'index.html'),
                 assets={f.name: sha(f) for f in sorted((dist/'assets').glob('index-*'))}),
        evidence=dict(cases=[c['id'] for c in index['cases']], sourceVerification='all saved cases verified',
                      railway=dict(interval=railway['interval'], browserVideoSha256=railway['video']['sha256'],
                                   sources={h['name']: h['sha256'] for h in railway['provenance']['hashes']})),
        video=dict(file=a.video.name, sha256=sha(a.video), durationSeconds=round(duration, 2), resolution=f'{size[0]}x{size[1]}'),
        native=dict(event='Adaptive Watch Review Required', alarmDefinition='Adaptive Watch review: station platform',
                    state=native['state'], alarm=native.get('alarmId'), payloadSha256=native.get('payloadSha256'),
                    notVerified='Playback association and bounding-box overlay: the 22 Oct recording is past retention.'),
        verification=dict(pythonTests=a.tests, browserChecks=a.checks),
        notClaimed=['validated false-negative reduction', 'independent accuracy benchmark', 'production deployment',
                    'a live Hafnia request from the browser (needs the operator-supplied gateway password)'])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(commit=manifest['commit'][:10], video=manifest['video'])))


if __name__ == '__main__':
    main()
