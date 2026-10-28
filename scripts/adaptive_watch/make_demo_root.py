"""Create an isolated demo copy of the railway review in its pending state (original database untouched)."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, default=Path('runs/negative-result-review'))
p.add_argument('--target', type=Path, default=Path('runs/release/demo-railway'))
a = p.parse_args()
if a.target.exists():
    shutil.rmtree(a.target)
a.target.mkdir(parents=True)
db = sqlite3.connect(a.target/'review.sqlite3')
src = sqlite3.connect(f'file:{(a.source/"review.sqlite3").resolve().as_posix()}?mode=ro', uri=True)
db.execute('CREATE TABLE review (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT, digest TEXT, state TEXT)')
db.execute('CREATE TABLE review_audit (id INTEGER PRIMARY KEY, at TEXT, action TEXT, document TEXT)')
record, digest_, state = src.execute('SELECT record,digest,state FROM review').fetchone()
state = json.loads(state)
state.update(status='review_required', reviewed=False, humanAnnotation=None, version=0)
db.execute('INSERT INTO review VALUES (1,?,?,?)', (record, digest_, json.dumps(state)))
db.commit()
print('Demo review copy ready at', a.target)
