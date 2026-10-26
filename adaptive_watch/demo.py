"""Isolated, offline browser replay of validated saved evidence. No network clients."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from adaptive_watch import episodes
from adaptive_watch.incident import sha


class Demo:
    def __init__(self, root, source, evaluations):
        self.root = Path(root).resolve()
        source = Path(source).resolve()
        if self.root == source or self.root.is_relative_to(source) or source.is_relative_to(self.root):
            raise ValueError('Demo and real evidence directories must be separate')
        self.root.mkdir(parents=True, exist_ok=True)
        self.saved = []
        db = sqlite3.connect(f'file:{(source / "evidence.sqlite3").as_posix()}?mode=ro', uri=True)
        try:
            for (raw,) in db.execute('SELECT document FROM observations ORDER BY id'):
                d = json.loads(raw)
                if d['evidenceKind'] != 'saved_retrospective':
                    continue
                if any(x['cameraGuid'] == d['cameraGuid'] for x in self.saved):
                    continue
                for key, expected in [('joined','joinedSha256'), ('cv','cvSha256'), ('manifest','manifestSha256')]:
                    if sha(d['provenance'][key]) != d[expected]:
                        raise ValueError('Saved source changed')
                # Re-run the full importer, including raw Hafnia and frame validation.
                from adaptive_watch.evidence_api import EvidenceStore
                joined = json.loads(Path(d['provenance']['joined']).read_text(encoding='utf-8-sig'))
                hashes = {h['source_sha256'] for h in joined['hafnia']}
                # Raw assessment locations are supplied by administrator seed setup.
                raw_dir = Path(evaluations).resolve()
                candidates = {sha(p) for p in raw_dir.glob('*.json')}
                if not hashes <= candidates:
                    raise ValueError('Original saved Hafnia records unavailable')
                validation = EvidenceStore(self.root / 'validation')
                try:
                    identifier = validation.register(d['provenance']['joined'], d['provenance']['cv'], d['provenance']['manifest'], raw_dir)
                    d = validation.get(identifier)['observations'][0]
                finally:
                    validation.close()
                self.saved.append(d)
        finally:
            db.close()
        if {d['camera'] for d in self.saved} != {'escooter_left_across_sidewalk', 'bin_pushed_over_onto_sidewalk'}:
            raise ValueError('Replay requires exactly two verified saved incidents')
        if not (self.root / 'active.json').exists():
            self.reset()

    def active(self):
        name = json.loads((self.root / 'active.json').read_text())
        if not isinstance(name, str) or len(name) != 32 or any(c not in '0123456789abcdef' for c in name):
            raise ValueError('Invalid demo session')
        return self.root / name

    def reset(self):
        name = uuid4().hex
        directory = self.root / name
        directory.mkdir()
        db = sqlite3.connect(directory / 'evidence.sqlite3')
        episodes.initialize(db)
        db.execute('CREATE TABLE replay (cursor INTEGER NOT NULL)')
        db.execute('INSERT INTO replay VALUES (0)')
        db.commit()
        db.close()
        temporary = self.root / 'active.tmp'
        temporary.write_text(json.dumps(name))
        temporary.replace(self.root / 'active.json')

    def status(self, db):
        cursor = db.execute('SELECT cursor FROM replay').fetchone()[0]
        return dict(mode='replay', session=self.active().name, cursor=cursor, total=6, complete=cursor == 6,
                    nativeActionAvailable=False, nativeReason='Replay cannot send XProtect events.',
                    provenance='Saved XProtect frames, local CV and recorded Hafnia responses. Repeat arrivals are synthetic and add no independent evidence.')

    def advance(self, db, expected):
        cursor = self.status(db)['cursor']
        if expected != cursor or cursor >= 6:
            raise ValueError('Replay changed; refresh')
        d = deepcopy(self.saved[cursor // 3])
        # Distinct fixture identity demonstrates grouping without altering source claims.
        d.update(syntheticFixture=True, loopReset=True, independentEvidence=False,
                 dispatchReviewReady=False, evidenceKind='replay',
                 title='E-scooter left on the pavement' if 'escooter' in d['camera'] else 'Bin tipped onto the pavement')
        d['replayArrivalId'] = str(cursor)
        episodes.ingest(db, d)
        with db:
            db.execute('UPDATE replay SET cursor=?', (cursor + 1,))
