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

from adaptive_watch.assessment_job import StageError
from adaptive_watch.casebook import Casebook
from adaptive_watch.negative_review import Conflict, ReviewStore
from adaptive_watch.workspace_api import handler as workspace_handler


def handler(repo, root, railway, evaluations, frontend, release, jobs=None, native=None):
    Base = workspace_handler(repo, root, railway, evaluations, frontend)
    import threading
    lock = threading.RLock()

    class Handler(Base):
        def book(self):
            return Casebook(repo, root, railway, evaluations, release)

        def present(self, case):
            """Add what the browser may do right now. Sending needs a saved request, a configured alarm and an enabled session."""
            n = case.get('native')
            if n is not None:
                saved = case['state'].get('status') in ('xprotect_review_requested', 'review_request_saved')
                n['canSend'] = bool(native and native.enabled and saved and n['state'] == 'configured' and case.get('handoff'))
            return case

        def camera_guid(self, case):
            from adaptive_watch.negative_review import read
            rows = [c for c in read(Path(repo)/'cameras.local.json') if c['Name'] == case['camera']]
            if len(rows) != 1:
                raise ValueError('The source camera is not in the authorized local catalog')
            return rows[0]['Id']

        def native_post(self, case_id):
            if not self.allowed():
                return self.reply(dict(error='Local same-origin access required'), 403)
            if not self.csrf_ok():
                return self.reply(dict(error='Reload the page to start a new local session'), 403)
            book = self.book()
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a small JSON request')
                body = json.loads(self.rfile.read(length))
                case = book.view(case_id)
                if native is None or not case.get('handoff') or not case['vision'] or not case['vision'].get('trigger'):
                    raise ValueError('This assessment has no XProtect review event to send')
                guid = self.camera_guid(case)
                if body.get('action') == 'preview':
                    return self.workspace_reply(dict(preview=native.preview(case, guid, include_box=case_id.startswith('live-'))))
                if body.get('action') != 'send' or body.get('confirmed') is not True:
                    raise ValueError('Explicit confirmation required')
                if case['state'].get('status') not in ('xprotect_review_requested', 'review_request_saved'):
                    raise ValueError('Save the review request before sending')
                if case['native']['state'] != 'configured':
                    raise ValueError('The XProtect alarm is not configured for this camera')
                with lock:
                    native.send(case, case_id, guid, str(body.get('approval', '')), include_box=case_id.startswith('live-'))
                return self.workspace_reply(dict(case=self.present(book.view(case_id))))
            except KeyError:
                self.reply(dict(error='Unknown assessment'), 404)
            except Exception as exc:
                from scene_contracts.analytics_event import AnalyticsEventError
                if isinstance(exc, (ValueError, AnalyticsEventError)):
                    self.reply(dict(error=str(exc)), 422)
                else:
                    raise
            finally:
                book.close()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ('/api/casebook', '/api/health') or re.fullmatch(r'/api/cases/[a-z][a-z0-9-]*(/.*)?', path):
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
                m = re.fullmatch(r'/api/cases/([a-z][a-z0-9-]*)', path)
                if m:
                    return self.workspace_reply(dict(case=self.present(book.view(m[1]))))
                m = re.fullmatch(r'/api/cases/(live-[0-9a-f]{8})/(video|frames/\d+)', path)
                if m:
                    files = book.live_files(m[1])
                    if m[2] == 'video':
                        return self.file(files['video'])
                    i = int(m[2].split('/')[1])
                    return self.file(files['frames'][i]) if i < len(files['frames']) else self.reply(dict(error='Frame not found'), 404)
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
            m = re.fullmatch(r'/api/jobs/([0-9a-f]{32})/(video|frames/\d+)', path)
            if m:
                try:
                    if m[2] == 'video':
                        return self.file(jobs.video_path(m[1]))
                    paths = jobs.contact_frames(m[1])
                    i = int(m[2].split('/')[1])
                    return self.file(paths[i]) if i < len(paths) else self.reply(dict(error='Frame not found'), 404)
                except KeyError:
                    return self.reply(dict(error='Not available yet'), 404)
                except (ValueError, OSError, StageError):
                    return self.reply(dict(error='Source files failed verification.'), 422)
            m = re.fullmatch(r'/api/jobs/([0-9a-f]{32})', path)
            if not m:
                return self.reply(dict(error='Unknown route'), 404)
            job = jobs.get(m[1])
            return self.workspace_reply(dict(job=job)) if job else self.reply(dict(error='Unknown analysis'), 404)

        def do_POST(self):
            path = urlsplit(self.path).path
            n = re.fullmatch(r'/api/cases/([a-z][a-z0-9-]*)/native', path)
            if n:
                return self.native_post(n[1])
            m = re.fullmatch(r'/api/cases/([a-z][a-z0-9-]*)/action', path)
            if m and m[1] == 'railway':
                return self.railway_action()
            if m and m[1].startswith('live-'):
                return self.railway_action(m[1])
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

        def railway_action(self, live_id=None):
            if not self.allowed():
                return self.reply(dict(error='Local same-origin access required'), 403)
            if not self.csrf_ok():
                return self.reply(dict(error='Reload the page to start a new local session'), 403)
            store = ReviewStore(railway) if not live_id else None
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a small JSON action')
                body = json.loads(self.rfile.read(length))
                if body.get('action') == 'save_review_request':
                    body['action'] = 'request_xprotect_review'
                body['annotation'] = {'condition_visible': 'entry_visible', 'condition_not_visible': 'entry_not_visible'}.get(body.get('annotation'), body.get('annotation'))
                book = self.book()
                try:
                    with lock:
                        if live_id:
                            return self.workspace_reply(dict(case=self.present(book.act_live(live_id, body))))
                        store.act(body)
                    self.workspace_reply(dict(case=self.present(book.view('railway'))))
                finally:
                    book.close()
            except Conflict as exc:
                self.reply(dict(error=str(exc)), 409)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self.reply(dict(error=str(exc) if isinstance(exc, ValueError) else 'Invalid review action'), 422)
            finally:
                if store:
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
            except StageError as exc:
                self.reply(dict(error=f'{exc.reason}. {exc.next}'), 422)
            except (ValueError, TypeError, KeyError) as exc:
                self.reply(dict(error=str(exc) if isinstance(exc, ValueError) else 'Invalid request'), 422)
            except Exception as exc:  # never drop the connection: say what failed and where to look
                import traceback
                traceback.print_exc()
                self.reply(dict(error=f'The assessment could not start ({type(exc).__name__}: {exc}). Details are in the server window.'), 500)

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
    p.add_argument('--gateway-prompt', action='store_true',
                   help='Ask once, in this terminal, for the Hafnia gateway password; kept in memory only. Enables New assessment.')
    p.add_argument('--native-send', action='store_true', help='Allow one confirmed review event to be sent to the Event Server.')
    p.add_argument('--event-target', default='127.0.0.1:9090', help='XProtect Event Server analytics host:port')
    a = p.parse_args()
    from adaptive_watch.assessment_job import Jobs
    from adaptive_watch.native_review import NativeReview
    factory = None
    if a.gateway_prompt:
        from scene_contracts.gateway import Gateway, GatewayError
        gateway = Gateway()
        try:
            gateway.authenticate(interactive_only=True)  # reads the password with getpass; never from the environment
        except GatewayError as exc:
            raise SystemExit(f'{exc}. Start again to retry.')
        factory = lambda: gateway
    jobs = Jobs(a.repo.resolve(), a.root.resolve(), gateway_factory=factory)
    server = ThreadingHTTPServer(('127.0.0.1', a.port), handler(a.repo.resolve(), a.root.resolve(), a.railway.resolve(),
                                                              a.evaluations.resolve(), a.frontend.resolve(), a.release.resolve(), jobs,
                                                              NativeReview(a.release.resolve(), a.event_target, a.native_send, a.root.resolve()/'native')))
    print(f'Adaptive Watch: http://127.0.0.1:{a.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
