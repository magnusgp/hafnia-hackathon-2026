"""Ortru application server: loopback only. Serves the interface and a small versioned JSON API.

Every JSON response has the same envelope: {schema, ok, data, error, csrf}. Authentication to Hafnia stays in this
process (entered once in the server window, never sent to the browser). XProtect is read only except for the one
confirmed native event per exception, through the duplicate-send ledger.
"""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from adaptive_watch.assessment_job import StageError
from ortru import SCHEMA, capabilities, policy
from ortru.exceptions import Reviews, Stale, build_view
from ortru.watches import Conflict, Watches

ID = r'[A-Za-z0-9-]{3,40}'


class App:
    """Everything the handler needs, built once. Tests construct it with fakes."""
    def __init__(self, repo, root, frontend, engine, watches, native, archive, catalog, runner, gateway_enabled, sending):
        self.repo, self.root, self.frontend = Path(repo), Path(root), Path(frontend)
        self.engine, self.watches, self.native, self.archive = engine, watches, native, archive
        self.catalog, self.runner, self.gateway_enabled, self.sending = catalog, runner, gateway_enabled, sending
        self.reviews = Reviews(engine)
        self.sessions, self.lock = set(), threading.RLock()
        self.snapshots = self.root/'snapshots'

    # -- views ----------------------------------------------------------------------------------
    def watch_view(self, w):
        return dict(w, schedule=self.engine.schedule_view(w), jobs=[j for j in self.engine.jobs(w['id'], 5)],
                    history=self.watches.history(w['id']), hasSnapshot=(self.snapshots/(w['config']['camera']['id'].lower()+'.jpg')).exists())

    def exception_view(self, job_id):
        d = self.reviews.get(job_id)
        view = build_view(self.engine, job_id, d)
        view['native'] = self.native.state(view) if view['handoff'] else dict(state='no_event', detail='Nothing to hand off.')
        view['decision'] = d
        return view

    def queue(self):
        """Raised exceptions (newest first), then the authentic archive records, each with its decision and native state."""
        live = []
        for j in self.engine.jobs(None, 200):
            if j['state'] != 'completed':
                continue
            try:
                v = self.exception_view(j['id'])
            except (ValueError, OSError, KeyError):
                live.append(dict(id=j['id'], origin='live', broken=True, reason='Source files failed verification. Restore the original recording and outputs for this assessment.'))
                continue
            if v['raised']:
                live.append(self.summary(v, 'live'))
        records = []
        for c in self.archive.entries()['cases'] if self.archive else []:
            if c['record']:
                try:
                    records.append(self.summary(self.archive.view(c['id']), 'archive'))
                except (ValueError, OSError, KeyError):
                    records.append(dict(id=c['id'], origin='archive', broken=True, reason='Source files failed verification.'))
        return dict(live=live, records=records)

    @staticmethod
    def summary(v, origin):
        return dict(id=v['id'], origin=origin, camera=v['camera'], at=v['at'], interval=v['interval'], reason=v['reason'],
                    watch=v.get('watch'), policy=v['policy'], hafniaTone=v['hafnia']['tone'], hafniaAnswer=v['hafnia']['answer'],
                    decision=v['decision']['status'], native=v['native']['state'] if v.get('native') else None,
                    smartClient=(v.get('native') or {}).get('smartClient'), title=v.get('title'))

    def bootstrap(self):
        return dict(capabilities=capabilities.listing(), policyKinds=[dict(id=k, label=policy.LABELS[k]) for k in policy.KINDS],
                    cameras=[dict(id=c['id'], name=c['name'], hasSnapshot=(self.snapshots/(c['id'].lower()+'.jpg')).exists(),
                                  native=self.watches.destinations.get(c['id'].lower())) for c in self.catalog],
                    watches=[self.watch_view(w) for w in self.watches.list()],
                    gateway=dict(available=self.gateway_enabled,
                                 reason=None if self.gateway_enabled else 'No Hafnia gateway session. Recordings are read and local vision runs; the Hafnia step waits.'),
                    native=dict(sending=self.sending, target=self.native.target), budget=dict(global_=self.engine.global_per_day, usedToday=self.engine.used_today()))


def handler(app):
    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a):
            pass

        # -- plumbing ---------------------------------------------------------------------------
        def allowed(self):
            port = self.server.server_port
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if self.headers.get('Host') not in hosts:
                return False
            return self.headers.get('Origin', f'http://127.0.0.1:{port}') in {'http://'+h for h in hosts} and self.headers.get('Sec-Fetch-Site') != 'cross-site'

        def token(self):
            c = SimpleCookie(self.headers.get('Cookie', ''))
            t = c['ortru_session'].value if 'ortru_session' in c else None
            with app.lock:
                if t not in app.sessions:
                    t = secrets.token_urlsafe(32)
                    app.sessions.add(t)
            return t

        def csrf_ok(self):
            c = SimpleCookie(self.headers.get('Cookie', ''))
            t = c['ortru_session'].value if 'ortru_session' in c else None
            return t in app.sessions and secrets.compare_digest(t, self.headers.get('X-Ortru-CSRF', ''))

        def reply(self, data=None, code=200, error=None):
            t = self.token()
            body = json.dumps(dict(schema=SCHEMA, ok=error is None, data=data, error=error, csrf=t), allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Set-Cookie', f'ortru_session={t}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(body)

        def fail(self, message, status=422, **extra):
            self.reply(None, status, error=dict(message=message, **extra))

        def file(self, path):
            path = Path(path)
            size = path.stat().st_size
            start, end, status = 0, size-1, 200
            asked = self.headers.get('Range')
            if asked:
                m = re.fullmatch(r'bytes=(\d+)-(\d*)', asked)
                if not m or int(m[1]) >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                start, end, status = int(m[1]), min(int(m[2]) if m[2] else size-1, size-1), 206
            self.send_response(status)
            self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            try:
                with path.open('rb') as f:
                    f.seek(start)
                    left = end-start+1
                    while left:
                        block = f.read(min(left, 65536))
                        if not block:
                            break
                        self.wfile.write(block)
                        left -= len(block)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def body(self):
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 32768 or self.headers.get('Content-Type') != 'application/json':
                raise ValueError('Expected a small JSON request')
            value = json.loads(self.rfile.read(n))
            if not isinstance(value, dict):
                raise ValueError('Expected a JSON object')
            return value

        # -- routing ----------------------------------------------------------------------------
        def do_GET(self):
            if not self.allowed():
                return self.fail('Local same-origin access required', 403)
            path = urlsplit(self.path).path
            try:
                if path.startswith('/api/'):
                    return self.api_get(path)
                asset = (app.frontend/('index.html' if path == '/' else path.lstrip('/'))).resolve()
                if asset.is_relative_to(app.frontend.resolve()) and asset.is_file() and asset.suffix in {'.html', '.js', '.css', '.woff', '.woff2', '.svg', '.ico', '.png'}:
                    return self.file(asset)
                if path == '/favicon.ico':
                    return self.file(app.frontend/'favicon.svg')
                self.fail('Not found', 404)
            except KeyError:
                self.fail('Not found', 404)
            except (ValueError, OSError):
                self.fail('Source files failed verification. Restore the original recording, response and vision output for this record.')

        def api_get(self, path):
            if path == '/api/ortru':
                return self.reply(app.bootstrap())
            if path == '/api/queue':
                return self.reply(app.queue())
            if path == '/api/archive':
                return self.reply(app.archive.entries() if app.archive else dict(cases=[], unavailable=[]))
            m = re.fullmatch(rf'/api/watches/({ID})', path)
            if m:
                return self.reply(app.watch_view(app.watches.get(m[1])))
            m = re.fullmatch(rf'/api/watches/({ID})/snapshot', path)
            if m:
                cam = app.watches.get(m[1])['config']['camera']['id'].lower() if m[1].startswith('w-') else m[1].lower()
                return self.file(app.snapshots/(cam+'.jpg'))
            m = re.fullmatch(r'/api/cameras/([0-9a-fA-F-]{36})/snapshot', path)
            if m:
                return self.file(app.snapshots/(m[1].lower()+'.jpg'))
            if path == '/api/jobs':
                return self.reply(app.engine.jobs())
            m = re.fullmatch(r'/api/jobs/([0-9a-f]{32})', path)
            if m:
                j = app.engine.get(m[1])
                return self.reply(j) if j else self.fail('Unknown assessment', 404)
            m = re.fullmatch(rf'/api/exceptions/([0-9a-f]{{32}})', path)
            if m:
                return self.reply(app.exception_view(m[1]))
            m = re.fullmatch(r'/api/exceptions/([0-9a-f]{32})/(video|frames/\d+)', path)
            if m:
                view = build_view(app.engine, m[1])
                d = app.engine.dir(m[1])
                job = json.loads((d/'job.json').read_text(encoding='utf-8'))
                if m[2] == 'video':
                    return self.file(d/'media/original.mp4')
                manifest = d/job['manifest']
                frames = json.loads(manifest.read_text(encoding='utf-8'))['frames']
                i = int(m[2].split('/')[1])
                return self.file(manifest.parent/frames[i]['file']) if i < len(frames) else self.fail('Frame not found', 404)
            m = re.fullmatch(rf'/api/archive/({ID})', path)
            if m:
                return self.reply(app.archive.view(m[1]))
            m = re.fullmatch(rf'/api/archive/({ID})/(video|frames/\d+)', path)
            if m:
                if m[2] == 'video':
                    return self.file(app.archive.video_path(m[1]))
                return self.file(app.archive.frame_path(m[1], int(m[2].split('/')[1])))
            self.fail('Unknown route', 404)

        def do_POST(self):
            self.mutate('POST')

        def do_PUT(self):
            self.mutate('PUT')

        def mutate(self, method):
            if not self.allowed():
                return self.fail('Local same-origin access required', 403)
            if not self.csrf_ok():
                return self.fail('Reload the page to start a new local session', 403)
            path = urlsplit(self.path).path
            try:
                body = self.body()
                with app.lock:
                    return self.api_write(method, path, body)
            except Conflict as exc:
                self.fail(str(exc), 409, code='stale_version')
            except Stale as exc:
                self.fail(str(exc), 409, code='stale_revision')
            except StageError as exc:
                self.fail(f'{exc.reason}. {exc.next}')
            except KeyError:
                self.fail('Not found', 404)
            except (ValueError, TypeError, OSError) as exc:
                self.fail(str(exc) if isinstance(exc, ValueError) else 'Invalid request')
            except Exception as exc:  # never drop the connection
                import traceback
                traceback.print_exc()
                self.fail(f'The request failed ({type(exc).__name__}). Details are in the server window.', 500)

        def api_write(self, method, path, body):
            if method == 'POST' and path == '/api/watches':
                return self.reply(app.watch_view(app.watches.create(body)))
            m = re.fullmatch(rf'/api/watches/({ID})', path)
            if method == 'PUT' and m:
                return self.reply(app.watch_view(app.watches.edit(m[1], body.get('baseVersion'), body.get('config'))))
            m = re.fullmatch(rf'/api/watches/({ID})/status', path)
            if m:
                w = app.watches.set_status(m[1], body.get('status'), body.get('baseVersion'))
                return self.reply(app.watch_view(w))
            m = re.fullmatch(rf'/api/watches/({ID})/run', path)
            if m:
                job = app.engine.start(m[1], trigger='manual')
                return self.reply(dict(job=app.engine.get(job['id']), created=job['created']))
            m = re.fullmatch(rf'/api/(watches|cameras)/({ID})/snapshot', path)
            if m:
                guid = (app.watches.get(m[2])['config']['camera'] if m[1] == 'watches' else None)
                cam = next((c for c in app.catalog if c['id'].lower() == m[2].lower()), None) if m[1] == 'cameras' else guid
                if not cam:
                    raise KeyError(m[2])
                out = app.snapshots/(cam['id'].lower()+'.jpg')
                _, at = app.runner.snapshot(cam['name'], out)
                return self.reply(dict(at=at))
            m = re.fullmatch(r'/api/jobs/([0-9a-f]{32})/discard', path)
            if m:
                return self.reply(app.engine.discard(m[1]))
            m = re.fullmatch(r'/api/jobs/([0-9a-f]{32})/retry', path)
            if m:
                return self.reply(app.engine.retry(m[1]))
            m = re.fullmatch(r'/api/exceptions/([0-9a-f]{32})/decision', path)
            if m:
                view = build_view(app.engine, m[1], app.reviews.get(m[1]))
                app.reviews.decide(m[1], body, view)
                return self.reply(app.exception_view(m[1]))
            m = re.fullmatch(r'/api/exceptions/([0-9a-f]{32})/native', path)
            if m:
                view = app.exception_view(m[1])
                if not view['handoff']:
                    raise ValueError('This assessment has nothing to hand off')
                if body.get('action') == 'preview':
                    return self.reply(dict(preview=app.native.preview(view), exception=view))
                if body.get('action') != 'send' or body.get('confirmed') is not True:
                    raise ValueError('Explicit confirmation is required')
                if view['decision']['status'] != 'review_requested':
                    raise ValueError('Save your decision to send to XProtect first')
                app.native.send(view, str(body.get('approval', '')))
                return self.reply(dict(exception=app.exception_view(m[1])))
            self.fail('Unknown route', 404)
    return H


def serve(app, port):
    server = ThreadingHTTPServer(('127.0.0.1', port), handler(app))

    def ticker():
        while True:
            time.sleep(30)
            try:
                app.engine.tick()
            except Exception:
                import traceback
                traceback.print_exc()
    threading.Thread(target=ticker, daemon=True).start()
    return server


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--root', type=Path, default=Path('runs/ortru'))
    p.add_argument('--archive', type=Path, default=None, help='Prepared archive copy (scripts/ortru_prepare.py)')
    p.add_argument('--data-repo', type=Path, default=None, help='Checkout that holds the private runs/ data and tooling (default: --repo)')
    p.add_argument('--evaluations', type=Path, default=Path.home()/'adaptive-watch-private/hafnia-16')
    p.add_argument('--cameras', type=Path, default=None, help='Authorized camera catalog (cameras.local.json)')
    p.add_argument('--ledger', type=Path, default=None, help='Shared duplicate-send ledger (default: runs/release/native/ledger.sqlite3 of --data-repo)')
    p.add_argument('--destinations', type=Path, default=None, help='Verified XProtect destinations (JSON: camera GUID to alarm name)')
    p.add_argument('--frontend', type=Path, default=Path('frontend/dist'))
    p.add_argument('--port', type=int, default=8790)
    p.add_argument('--gateway-prompt', action='store_true', help='Ask once, in this terminal, for the Hafnia gateway password.')
    p.add_argument('--native-send', action='store_true', help='Allow one confirmed review event to be sent to the Event Server.')
    p.add_argument('--event-target', default='127.0.0.1:9090')
    a = p.parse_args()
    repo, root = a.repo.resolve(), a.root.resolve()
    data = (a.data_repo or a.repo).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cam_file = a.cameras or (root/'cameras.local.json' if (root/'cameras.local.json').exists() else data/'cameras.local.json')
    cams = json.loads(cam_file.read_text(encoding='utf-8-sig'))
    catalog = [dict(id=c['Id'], name=c['Name']) for c in cams]
    dest = {}
    dpath = a.destinations or root/'destinations.json'
    if dpath.exists():
        dest = {k.lower(): v for k, v in json.loads(dpath.read_text(encoding='utf-8-sig')).items()}
    watches = Watches(root/'ortru.sqlite3', catalog, dest)
    factory = None
    if a.gateway_prompt:
        from scene_contracts.gateway import Gateway, GatewayError
        gateway = Gateway()
        try:
            gateway.authenticate(interactive_only=True)  # reads the password with getpass; never from the environment
        except GatewayError as exc:
            raise SystemExit(f'{exc}. Start again to retry.')
        factory = lambda: gateway
    from ortru.effects import OrtruEffects
    from ortru.engine import Engine
    from ortru.native import Native
    runner = OrtruEffects(repo, deps=data/'runs/tooling/pydeps' if (data/'runs/tooling/pydeps').exists() else None, private=data)
    engine = Engine(root, watches, runner, gateway_factory=factory)
    native = Native((a.ledger or data/'runs/release/native/ledger.sqlite3').resolve(), a.event_target, a.native_send, root/'native-status.json', dest)
    archive = None
    if a.archive:
        from ortru.archive import Archive
        ar = a.archive.resolve()
        archive = Archive(data, ar/'app', ar/'railway', ar/'release', a.evaluations.resolve())
    app = App(repo, root, a.frontend.resolve(), engine, watches, native, archive, catalog, runner, factory is not None, a.native_send)
    server = serve(app, a.port)
    print(f'Ortru: http://127.0.0.1:{a.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
