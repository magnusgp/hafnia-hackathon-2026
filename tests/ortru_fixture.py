"""Isolated Ortru server for browser acceptance tests.

Real HTTP server and real engine, store, policy and views, but: fake XProtect/GPU/Hafnia effects, a stand-in
original recording, and a test transport that cannot reach the Event Server (it records the POST in memory).
Never the operator's data: everything lives in a fresh temporary root.

    .venv\\Scripts\\python.exe -m tests.ortru_fixture --port 8795 [--archive runs/ortru/archive --data-repo <checkout>] [--video file.mp4]
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from ortru.engine import Engine
from ortru.native import Native
from ortru.server import App, serve
from ortru.watches import Watches
from tests.test_ortru import CATALOG, DEST, FakeConnection, FakeGateway, FakeRunner, sha


class Fixture(FakeRunner):
    def __init__(self, video=None, **kw):
        super().__init__(**kw)
        self.video = Path(video) if video else None

    def encode(self, manifest, out):
        if not self.video:
            return super().encode(manifest, out)
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.video, out/'original.mp4')
        m = json.loads(Path(manifest).read_text())
        info = dict(file='original.mp4', sha256=sha((out/'original.mp4').read_bytes()), sourceMkvSha256=m['mkv_export']['sha256'], fps=10, frames=150,
                    duration=15.0, samples=[dict(index=i, timestamp=f['timestamp_utc'], mediaTime=round(i*.5, 1), matchError=1.0) for i, f in enumerate(m['frames'])])
        (out/'media.json').write_text(json.dumps(info))
        return info, [1.0+(i % 3)*.1 for i in range(149)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8795)
    p.add_argument('--archive', type=Path)
    p.add_argument('--data-repo', type=Path)
    p.add_argument('--video', type=Path)
    p.add_argument('--no-gateway', action='store_true')
    p.add_argument('--frontend', type=Path, default=Path('frontend/dist'))
    a = p.parse_args()
    root = Path(tempfile.mkdtemp(prefix='ortru-fixture-'))
    watches = Watches(root/'ortru.sqlite3', CATALOG, DEST)
    runner = Fixture(a.video)
    gateway = FakeGateway()  # one instance, so every request gets a new summary id like the real gateway
    engine = Engine(root, watches, runner, gateway_factory=None if a.no_gateway else (lambda: gateway))
    native = Native(root/'ledger.sqlite3', '127.0.0.1:9090', True, root/'status.json', DEST, connection=FakeConnection)
    archive = None
    if a.archive:
        from ortru.archive import Archive
        ar = a.archive.resolve()
        archive = Archive((a.data_repo or Path('.')).resolve(), ar/'app', ar/'railway', ar/'release', Path.home()/'adaptive-watch-private/hafnia-16')
    app = App(root, root, a.frontend.resolve(), engine, watches, native, archive, CATALOG, runner, not a.no_gateway, True)
    server = serve(app, a.port)
    print(f'Ortru fixture: http://127.0.0.1:{a.port} (root {root}; POSTs to the Event Server are captured in memory, never sent)', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
