"""Local single-case operator API. Cannot configure XProtect or send native events."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit

from adaptive_watch.negative_review import Conflict, ReviewStore


def handler(root, frontend):
    frontend = Path(frontend).resolve()
    sessions, lock = set(), threading.RLock()

    class Handler(BaseHTTPRequestHandler):
        def allowed(self):
            origins = {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in {urlsplit(o).netloc for o in origins}:
                return False
            return self.headers.get('Origin',next(iter(origins))) in origins and self.headers.get('Sec-Fetch-Site') != 'cross-site'

        def reply(self, value, code=200, cookie=None):
            data = json.dumps(value,allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if cookie:
                self.send_header('Set-Cookie',f'aw_review={cookie}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(data)

        def file(self,path):
            size = path.stat().st_size
            start,end,status = 0,size-1,200
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
                if not match or int(match[1]) >= size:
                    self.send_response(416)
                    self.send_header('Content-Range',f'bytes */{size}')
                    self.end_headers()
                    return
                start = int(match[1]); end = min(int(match[2]) if match[2] else size-1,size-1)
                if end < start:
                    self.send_error(416); return
                status = 206
            self.send_response(status)
            self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(end-start+1))
            self.send_header('Accept-Ranges','bytes')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            if status == 206:
                self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            try:
                with path.open('rb') as f:
                    f.seek(start)
                    remaining = end-start+1
                    while remaining:
                        block = f.read(min(remaining,65536))
                        if not block:
                            break
                        self.wfile.write(block); remaining -= len(block)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
                pass

        def do_GET(self):
            if not self.allowed():
                self.reply(dict(error='Local same-origin access required'),403); return
            path = urlsplit(self.path).path
            store = ReviewStore(root)
            try:
                if path == '/api/review':
                    view = store.view()
                    cookie = SimpleCookie()
                    cookie.load(self.headers.get('Cookie',''))
                    token = cookie['aw_review'].value if 'aw_review' in cookie else None
                    with lock:
                        if token not in sessions:
                            token = secrets.token_urlsafe(32)
                            sessions.add(token)
                    self.reply(dict(review=view,csrf=token),cookie=token)
                elif path.startswith('/api/review/'):
                    record,_ = store.verified()
                    if path == '/api/review/video':
                        self.file(Path(record['media']['path']))
                    elif path == '/api/review/original':
                        self.file(Path(record['originalVideo']))
                    elif re.fullmatch(r'/api/review/frames/\d+',path):
                        index = int(path.rsplit('/',1)[1])
                        if index >= len(record['frames']):
                            self.reply(dict(error='Frame not found'),404)
                        else:
                            self.file(Path(record['frames'][index]['path']))
                    else:
                        self.reply(dict(error='Route not found'),404)
                else:
                    asset = (frontend/('index.html' if path == '/' else path.lstrip('/'))).resolve()
                    if asset.is_relative_to(frontend) and asset.is_file() and asset.suffix in {'.html','.js','.css','.woff','.woff2','.svg','.ico'}:
                        self.file(asset)
                    elif path == '/favicon.ico':
                        self.send_response(204); self.end_headers()
                    else:
                        self.reply(dict(error='Route not found'),404)
            except Conflict as exc:
                self.reply(dict(error=str(exc)),409)
            except (ValueError,OSError,KeyError) as exc:
                self.reply(dict(error='Evidence unavailable; verify persisted sources before reviewing'),422)
            finally:
                store.close()

        def do_POST(self):
            if not self.allowed():
                self.reply(dict(error='Local same-origin access required'),403); return
            if urlsplit(self.path).path != '/api/review/action':
                self.reply(dict(error='Native configuration and dispatch are unavailable'),403); return
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie',''))
                token = cookie['aw_review'].value
                if token not in sessions or not secrets.compare_digest(token,self.headers.get('X-Review-CSRF','')):
                    raise ValueError()
            except (KeyError,ValueError):
                self.reply(dict(error='Valid local review session required'),403); return
            store = ReviewStore(root)
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a small JSON review action')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body,dict):
                    raise ValueError('Expected a review action object')
                with lock:
                    view = store.act(body)
                self.reply(dict(review=view))
            except Conflict as exc:
                self.reply(dict(error=str(exc)),409)
            except (ValueError,TypeError,KeyError,OSError) as exc:
                self.reply(dict(error=str(exc) if isinstance(exc,ValueError) else 'Invalid review action'),422)
            finally:
                store.close()

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('runs/negative-review'))
    p.add_argument('--frontend',type=Path,default=Path('frontend/dist'))
    p.add_argument('--port',type=int,default=8772)
    a = p.parse_args()
    store = ReviewStore(a.root)
    try:
        store.view()
    finally:
        store.close()
    server = ThreadingHTTPServer(('127.0.0.1',a.port),handler(a.root,a.frontend))
    print(f'Negative-result review: http://127.0.0.1:{a.port}',flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
