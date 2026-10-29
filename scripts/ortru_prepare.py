"""Build Ortru's private archive copy from the operator state, read only.

Copies (never moves, never opens for writing) the railway review database via the SQLite backup API, the completed live
assessment folders, the saved native send status and the browser media into runs/ortru/archive. Seeds
runs/ortru/destinations.json from the verified native configuration. Original files are untouched.

    .venv\\Scripts\\python.exe scripts\\ortru_prepare.py --source C:\\path\\to\\main\\checkout
"""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True, help='Checkout that holds runs/ (the operator state)')
p.add_argument('--target', type=Path, default=Path('runs/ortru'))
a = p.parse_args()
src, out = a.source.resolve(), a.target.resolve()
arch = out/'archive'
if arch.exists():
    shutil.rmtree(arch)
for d in ('app/native', 'railway', 'release/native', 'release/media'):
    (arch/d).mkdir(parents=True)


def copy_db(from_path, to_path):
    ro = sqlite3.connect(f'file:{from_path.as_posix()}?mode=ro', uri=True)
    dst = sqlite3.connect(to_path)
    ro.backup(dst)
    dst.close()
    ro.close()


copy_db(src/'runs/negative-result-review/review.sqlite3', arch/'railway/review.sqlite3')
if (src/'runs/negative-result-review/media').exists():
    shutil.copytree(src/'runs/negative-result-review/media', arch/'railway/media')
app = src/'runs/release/app'
shutil.copytree(app/'live', arch/'app/live')
if (app/'workspace.sqlite3').exists():
    copy_db(app/'workspace.sqlite3', arch/'app/workspace.sqlite3')
else:
    sqlite3.connect(arch/'app/workspace.sqlite3').close()
shutil.copyfile(app/'native/status.json', arch/'app/native/status.json')
shutil.copytree(src/'runs/release/media', arch/'release/media', dirs_exist_ok=True)
shutil.copyfile(src/'runs/release/native/config.json', arch/'release/native/config.json')
cfg = json.loads((src/'runs/release/native/config.json').read_text(encoding='utf-8-sig'))
cams = {c['Name']: c['Id'] for c in json.loads((src/'cameras.local.json').read_text(encoding='utf-8-sig'))}
dest = {}
if cfg.get('railway', {}).get('configured') is True:
    dest[cams['person_on_railway_tracks'].lower()] = cfg['railway']['alarmDefinition']
(out/'destinations.json').write_text(json.dumps(dest, indent=2), encoding='utf-8')
shutil.copyfile(src/'cameras.local.json', out/'cameras.local.json')
print('Archive copy ready at', arch, '; destinations:', dest)
