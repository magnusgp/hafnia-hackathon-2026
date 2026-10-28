"""Adaptive Watch application server: loopback only, one casebook, case-scoped local decisions.

Serves the built interface, the unified case view model, original media, and local review actions.
It cannot configure XProtect. Native sends use the guarded CLI in scripts/adaptive_watch.
"""
import argparse
import json
from pathlib import Path
import re
import sqlite3
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from adaptive_watch.casebook import Casebook
from adaptive_watch.negative_review import Conflict, ReviewStore
from adaptive_watch.workspace_api import handler as workspace_handler


def handler(repo, root, railway, evaluations, frontend, release, jobs=None):
    Base = workspace_handler(repo, root, railway, evaluations, frontend)
    import threading
    lock = threading.RLock()

    class Handler(Base):
        def book(self):
            return Casebook(repo, root, railway, evaluations, release)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ('/api/casebook', '/api/health') or re.fullmatch(r'/api/cases/[a-z]+(/.*)?', path):
                if not self.allowed():
                    return self.reply(dict(error='Local same-origin access required'), 403)
                return self.casebook_get(path)
            if jobs and path.startswith('/api/jobs'):
                if not self.allowed():
                    return self.reply(dict(error='Local same-origin access required'), 403)
                return self.jobs_get(path)
            return super().do_GET()

        def casebook_get(self, path):
            if path == '/api/health':
                return self.reply(dict(ok=True))
            book = self.book()
            try:
                if path == '/api/casebook':
                    return self.workspace_reply(book.index() | dict(assessment=jobs.options() if jobs else None))
                m = re.fullmatch(r'/api/cases/([a-z]+)', path)
                if m:
                    return self.workspace_reply(dict(case=book.view(m[1])))
                m = re.fullmatch(r'/api/cases/([a-z]+)/frames/(\d+)', path)
                if m:
                    view = book.view(m[1])
                    i = int(m[2])
                    if i >= len(view['frames']):
                        return self.reply(dict(error='Frame not found'), 404)
                    if m[1] == 'railway':
                        rs = ReviewStore(railway)
                        try:
                            record, _ = rs.verified()
                        finally:
                            rs.close()
                        return self.file(Path(record['frames'][i]['path']))
                    return self.file(Path(book.ws.view(m[1], private=True)['frames'][i]['path']))
                m = re.fullmatch(r'/api/cases/railway/video', path)
                if m:
                    view = book.view('railway')
                    return self.file(Path(release)/'media/railway/original.mp4')
                return self.reply(dict(error='Unknown route'), 404)
            except KeyError:
                self.reply(dict(error='Unknown assessment'), 404)
            except Conflict as exc:
                self.reply(dict(error=str(exc)), 409)
            except (ValueError, TypeError, OSError, sqlite3.Error, StopIteration):
                self.reply(dict(error='Source files failed verification. Restore the original recording, response and vision output for this case.'), 422)
            finally:
                book.close()

        def jobs_get(self, path):
            m = re.fullmatch(r'/api/jobs/([0-9a-f]{32})', path)
            if not m:
                return self.reply(dict(error='Unknown route'), 404)
            job = jobs.get(m[1])
            return self.workspace_reply(dict(job=job)) if job else self.reply(dict(error='Unknown analysis'), 404)

        def do_POST(self):
            path = urlsplit(self.path).path
            m = re.fullmatch(r'/api/cases/([a-z]+)/action', path)
            if m and m[1] == 'railway':
                return self.railway_action()
            if jobs and path in ('/api/jobs', '/api/jobs/continuity'):
                return self.job_post(path)
            return super().do_POST()

        def csrf_ok(self):
            from http.cookies import SimpleCookie
            import secrets
            try:
                token = SimpleCookie(self.headers.get('Cookie', ''))['aw_workspace'].value
            except KeyError:
                return False
            return token in self.sessions_ref() and secrets.compare_digest(token, self.headers.get('X-Review-CSRF', ''))

        def railway_action(self):
            if not self.allowed():
                return self.reply(dict(error='Local same-origin access required'), 403)
            if not self.csrf_ok():
                return self.reply(dict(error='Reload the page to start a new local session'), 403)
            store = ReviewStore(railway)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a small JSON action')
                body = json.loads(self.rfile.read(length))
                if body.get('action') == 'save_review_request':
                    body['action'] = 'request_xprotect_review'
                if body.get('annotation') in ('condition_visible',):
                    body['annotation'] = 'entry_visible'
                with lock:
                    store.act(body)
                book = self.book()
                try:
                    self.workspace_reply(dict(case=book.view('railway')))
                finally:
                    book.close()
            except Conflict as exc:
                self.reply(dict(error=str(exc)), 409)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self.reply(dict(error=str(exc) if isinstance(exc, ValueError) else 'Invalid review action'), 422)
            finally:
                store.close()

        def job_post(self, path):
            if not self.allowed():
                return self.reply(dict(error='Local same-origin access required'), 403)
            if not self.csrf_ok():
                return self.reply(dict(error='Reload the page to start a new local session'), 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a small JSON request')
                body = json.loads(self.rfile.read(length))
                result = jobs.start(body) if path == '/api/jobs' else jobs.confirm_continuity(body)
                self.reply(dict(job=result))
            except (ValueError, TypeError, KeyError) as exc:
                self.reply(dict(error=str(exc) if isinstance(exc, ValueError) else 'Invalid request'), 422)

        def sessions_ref(self):
            return type(self).sessions

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--root', type=Path, default=Path('runs/release/app'))
    p.add_argument('--railway', type=Path, default=Path('runs/negative-result-review'))
    p.add_argument('--evaluations', type=Path, required=True)
    p.add_argument('--frontend', type=Path, default=Path('frontend/dist'))
    p.add_argument('--release', type=Path, default=Path('runs/release'))
    p.add_argument('--port', type=int, default=8780)
    a = p.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', a.port), handler(a.repo.resolve(), a.root.resolve(), a.railway.resolve(),
                                                              a.evaluations.resolve(), a.frontend.resolve(), a.release.resolve()))
    print(f'Adaptive Watch: http://127.0.0.1:{a.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
