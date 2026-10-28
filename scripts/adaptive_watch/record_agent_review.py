"""Record the Claude demo reviewer's visual assessment of the railway footage (append-only).

The review text below was written after viewing the 2 Hz snapshots and the 10 fps original between
11:03:47.4 and 11:03:49.0 UTC. It is an AI assessment, kept apart from Hafnia's answer, the detector's
proximity trigger and any human decision.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adaptive_watch.casebook import Casebook

REVIEW = dict(
    reviewer='Claude demo reviewer',
    model='claude-sonnet-5-5',
    provenance='AI visual review of the original recording and its timestamped snapshots; not a human attestation.',
    decision='entry_visible',
    headline='The person climbs down onto the tracks and walks away along them.',
    decisiveMoment=dict(timestamp='2026-10-22T11:03:48.313Z', mediaTime=9.2,
                        what='Both feet reach the track bed after the person lowers themselves off the platform edge.'),
    phases=[
        dict(start='2026-10-22T11:03:42.013Z', end='2026-10-22T11:03:48.313Z', kind='edge', label='Seated on the platform edge'),
        dict(start='2026-10-22T11:03:48.313Z', end='2026-10-22T11:03:52.013Z', kind='tracks', label='On the tracks'),
    ],
    observations=[
        dict(timestamp='2026-10-22T11:03:41.013Z', sample=4, what='Walks to the yellow edge strip and crouches facing the tracks.'),
        dict(timestamp='2026-10-22T11:03:42.013Z', sample=6, what='Sits on the platform edge with their legs over the track side.'),
        dict(timestamp='2026-10-22T11:03:47.513Z', sample=17, what='Still seated at the edge; hands on the platform, lower legs below it.'),
        dict(timestamp='2026-10-22T11:03:48.013Z', sample=18, what='Lowers themselves off the edge; the lower body is below platform level.'),
        dict(timestamp='2026-10-22T11:03:48.313Z', sample=None, what='Feet on the track bed, body still turned toward the platform (original 10 fps frames).'),
        dict(timestamp='2026-10-22T11:03:48.513Z', sample=19, what='Upright on the track bed, walking away from the camera.'),
        dict(timestamp='2026-10-22T11:03:51.513Z', sample=25, what='Still walking along the tracks, far from the platform.'),
    ],
    basis='Frames 18 to 20 and the original frames at 48.1 to 48.5 s show a continuous lowering from the platform edge to standing on the track bed. Frames 21 to 25 show the same red-jacketed person walking along the tracks. Hafnia said the person stayed on the platform; the footage shows otherwise.',
    limits='One AI reviewer, one scripted scenario. The detector region is a draft and was not used for this decision.',
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT/'runs/release/app')
    p.add_argument('--railway', type=Path, default=ROOT/'runs/negative-result-review')
    p.add_argument('--evaluations', type=Path, required=True)
    p.add_argument('--release', type=Path, default=ROOT/'runs/release')
    a = p.parse_args()
    book = Casebook(ROOT, a.root, a.railway, a.evaluations, a.release)
    try:
        view = book.railway_view()
        existing = book.agent_review('railway', view['revision'])
        if existing and existing['currentSource']:
            print('Agent review already recorded for this source revision.')
            return
        book.record_agent_review('railway', REVIEW, view['revision'])
        print('Recorded agent review for', view['revision'][:12])
    finally:
        book.close()


if __name__ == '__main__':
    main()
