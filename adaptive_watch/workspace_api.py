"""Adaptive Watch multi-case workspace; loopback only, local review decisions."""
import argparse
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from urllib.parse import urlsplit

from adaptive_watch.assessment_entry import AssessmentEntry
from adaptive_watch.negative_review import Conflict
from adaptive_watch.negative_review_api import handler as railway_handler
from adaptive_watch.workspace import Workspace


def handler(repo, root, railway, evaluations, frontend):
    sessions, lock = set(), threading.RLock()
    Base = railway_handler(railway, frontend)

    class Handler(Base):
        def workspace(self):
            return Workspace(repo,root,railway,evaluations)

        def session(self):
            cookie = SimpleCookie(self.headers.get('Cookie',''))
            token = cookie['aw_workspace'].value if 'aw_workspace' in cookie else None
            with lock:
                if token not in sessions:
                    token = secrets.token_urlsafe(32)
                    sessions.add(token)
            return token

        def workspace_reply(self, data):
            token = self.session()
            # Base reply writes the railway cookie; use a dedicated cookie here.
            encoded = json.dumps(dict(**data,csrf=token),allow_nan=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Set-Cookie',f'aw_workspace={token}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            path = urlsplit(self.path).path
            if not (path.startswith('/api/cases') or path.startswith('/api/assessments') or path == '/api/workspace'):
                # Existing single-case routes remain available and unchanged.
                return super().do_GET()
            if not self.allowed():
                return self.reply(dict(error='Local same-origin access required'),403)
            store = self.workspace()
            try:
                if path == '/api/workspace':
                    return self.workspace_reply(store.index())
                if path == '/api/assessments/options':
                    return self.workspace_reply(AssessmentEntry(repo,root).configurations())
                match = re.fullmatch(r'/api/cases/([a-z]+)(?:/frames/(\d+))?',path)
                if not match:
                    return self.reply(dict(error='Unknown assessment route'),404)
                identifier, index = match.groups()
                if identifier == 'railway':
                    return self.reply(dict(error='Use the preserved railway evidence route'),404)
                record = store.view(identifier,private=index is not None)
                if index is not None:
                    if int(index) >= len(record['frames']):
                        return self.reply(dict(error='Frame not found for this assessment'),404)
                    return self.file(Path(record['frames'][int(index)]['path']))
                self.workspace_reply(dict(review=record))
            except KeyError:
                self.reply(dict(error='Unknown assessment or incomplete source data'),404)
            except Conflict as exc:
                self.reply(dict(error=str(exc)),409)
            except (ValueError,TypeError,OSError,sqlite3.Error,StopIteration):
                self.reply(dict(error='Insufficient evidence: original sources are unavailable or failed verification. Restore this case’s original recording, response and CV sources.'),422)
            finally:
                store.close()

        def do_POST(self):
            path = urlsplit(self.path).path
            if path.startswith('/api/review/'):
                return super().do_POST()
            if not self.allowed():
                return self.reply(dict(error='Local same-origin access required'),403)
            match = re.fullmatch(r'/api/cases/([a-z]+)/action',path)
            if not match and path != '/api/assessments':
                return self.reply(dict(error='Unsupported action; native dispatch unavailable'),403)
            try:
                cookie = SimpleCookie(self.headers.get('Cookie',''))
                token = cookie['aw_workspace'].value
                if token not in sessions or not secrets.compare_digest(token,self.headers.get('X-Review-CSRF','')):
                    raise ValueError()
            except (KeyError,ValueError):
                return self.reply(dict(error='Valid local workspace session required'),403)
            store = self.workspace()
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a small JSON action')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict):
                    raise ValueError('Expected an action object')
                with lock:
                    if match:
                        result = dict(review=store.act(match[1],body))
                    else:
                        result = dict(attempt=AssessmentEntry(repo,root).start(body))
                self.reply(result)
            except Conflict as exc:
                self.reply(dict(error=str(exc)),409)
            except KeyError:
                self.reply(dict(error='Unknown assessment'),404)
            except (ValueError,TypeError,OSError,sqlite3.Error,StopIteration) as exc:
                self.reply(dict(error=str(exc) if isinstance(exc,ValueError) else 'Action blocked: source data unavailable or invalid'),422)
            finally:
                store.close()
    return Handler


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--root',type=Path,default=Path('runs/application'))
    p.add_argument('--railway',type=Path,default=Path('runs/negative-result-review'))
    p.add_argument('--evaluations',type=Path,required=True,help='Original saved Hafnia evaluation directory')
    p.add_argument('--frontend',type=Path,default=Path('frontend/dist'))
    p.add_argument('--port',type=int,default=8777)
    a = p.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1',a.port),handler(a.repo.resolve(),a.root.resolve(),a.railway.resolve(),a.evaluations.resolve(),a.frontend.resolve()))
    print(f'Adaptive Watch workspace: http://127.0.0.1:{a.port}',flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
