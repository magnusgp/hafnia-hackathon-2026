"""Loopback-only Scene Contracts operator console (Python standard library)."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from scene_contracts.contracts import DEFAULT_CONTRACTS
from scene_contracts.operator import Operator
from scene_contracts.store import Store

ASSETS = Path(__file__).parent / 'scene_contracts' / 'static'


def h(value):
    return escape(str(value), quote=True)


def badge(value):
    return f'<span class="badge {h(value)}">{h(value.replace("_", " "))}</span>'


def details(title, value):
    return f'<details><summary>{h(title)}</summary><pre>{h(value if isinstance(value, str) else json.dumps(value, indent=2))}</pre></details>'


class Console:
    def __init__(self, operator, csrf):
        self.op, self.csrf = operator, csrf

    def form(self, action, content):
        return f'<form method="post" action="{action}"><input type="hidden" name="csrf" value="{self.csrf}">{content}</form>'

    def field(self, name, label, kind='text', value=''):
        return f'<label>{h(label)}<input name="{name}" type="{kind}" value="{h(value)}" required></label>'

    def select(self, name, label, options):
        return f'<div class="select-field"><label for="{name}">{label}</label><select id="{name}" name="{name}" required><option value="">Select…</option>' + ''.join(f'<option value="{h(key)}">{h(title)}</option>' for key, title in options) + '</select></div>'

    def page(self, title, body, active=''):
        nav = ''.join(f'<a {"aria-current=page" if active == path else ""} href="{path}">{label}</a>' for path, label in [('/', 'Review cases'), ('/contracts', 'Contracts'), ('/analyze', 'Analyze')])
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{h(title)} · Scene Contracts</title><link rel="stylesheet" href="/style.css"></head><body>
        <header><a class="brand" href="/">SC <span>Scene Contracts<small>HAFNIA · OPERATOR CONSOLE</small></span></a><span class="local">LOCAL WORKSPACE</span></header>
        <nav aria-label="Main navigation">{nav}</nav><main><div class="heading"><div><p class="eyebrow">CAMERA RESPONSIBILITY / RECORDED EVIDENCE</p><h1>{h(title)}</h1></div><a class="button" href="/analyze">New assessment</a></div>{body}</main><footer>Human review required · Recorded intervals only · Native events are not sent by this console</footer></body></html>'''

    def cases(self):
        cases = self.op.store.cases()
        counts = {state: sum(c['state'] == state for c in cases) for state in ('review_required', 'reviewed', 'observed')}
        body = '<div class="metrics">' + ''.join(f'<section><strong>{count}</strong><span>{state.replace("_", " ").title()}</span></section>' for state, count in counts.items()) + '</div>'
        body += '<section><h2>Evidence review queue</h2><p>Each case groups evidence for one camera responsibility. New findings can reopen review.</p>'
        if not cases:
            body += '<div class="empty">No evidence cases yet. Analyze a recorded interval or import a saved Hafnia result.</div>'
        else:
            body += '<div class="scroll"><table><thead><tr><th>Case / camera</th><th>Responsibility</th><th>Review state</th><th>Evidence</th></tr></thead><tbody>'
            for case in reversed(cases):
                evidence = self.op.store.case(case['id'])['observations']
                latest = evidence[-1]
                body += f'<tr><td><a href="/cases/{case["id"]}">#{case["id"]} · {h(latest["camera_name"])}</a></td><td>{h(latest["contract_json"]["name"])}</td><td>{badge(case["state"])}</td><td>{len(evidence)} assessment(s) · {badge(latest["outcome"])}</td></tr>'
            body += '</tbody></table></div>'
        body += '</section><section><h2>Recent requests</h2>'
        jobs = self.op.recent()
        body += ''.join(f'<p><a href="/requests/{h(j["id"])}">{h(j["created_at"][:19])} UTC</a> {badge(j["status"])} <span class="mono">{h(j["summary_id"] or "Not submitted")}</span></p>' for j in jobs) or '<p>No requests prepared.</p>'
        return self.page('Review cases', body + '</section>', '/')

    def contracts(self):
        body = '<p class="intro">Give each camera an observable responsibility. The fixed assessment format preserves evidence and uncertainty for operator review.</p>'
        for c in self.op.contracts():
            legacy = ' · Legacy v0.1 evidence format' if c.get('gateway_prompt_title') else ''
            body += f'<section><div class="section-heading"><h2>{h(c["name"])}</h2><span class="muted">v{h(c["version"])}{legacy}</span></div><p>{h(c["expected_condition"])}</p><p class="mono muted">{h(", ".join(c["camera_names"]))}</p>{details("Exact assessment prompt", c["assessment_prompt"])}</section>'
        camera_options = [(name, name) for name in self.op.cameras()]
        content = self.field('name', 'Contract name') + self.select('camera', 'Associated camera', camera_options) + '<label>Expected observable condition<textarea name="condition" maxlength="1000" rows="3" required placeholder="Describe what should remain visibly true in the recording"></textarea></label><p>The fixed template evaluates visible contradictions, supporting evidence and limitations. Saved contracts are immutable; create another to change policy.</p><button>Save contract and show exact prompt</button>'
        return self.page('Contracts', body + '<section><h2>Configure a responsibility</h2>' + self.form('/contracts', content) + '</section>', '/contracts')

    def analyze(self):
        content = self.select('contract', 'Contract', [(c['id'], c['name'] + (' (legacy evidence format)' if c.get('gateway_prompt_title') else '')) for c in self.op.contracts()])
        content += self.select('camera', 'Camera', [(name, name) for name in self.op.cameras()])
        content += '<div class="columns">' + self.field('start', 'Recording start · UTC (include Z)', value='') + self.field('end', 'Recording end · UTC (include Z)') + '</div><p>Use a verified recorded interval, for example YYYY-MM-DDTHH:MM:SSZ. Preview validates the camera and interval. It makes no gateway request.</p><button>Preview request</button>'
        body = '<section><h2>1 / Choose the responsibility and recording</h2>' + self.form('/preview', content) + '</section>'
        if not self.op.cameras():
            body = '<div class="notice">Camera catalog unavailable. Export Get-VmsCamera Name/Id to cameras.local.json on the VM. Existing evidence cases remain available.</div>' + body
        return self.page('Analyze recorded scene', body, '/analyze')

    def assessment(self, obs):
        a = obs['assessment']
        body = f'<article class="assessment"><div class="section-heading"><h3>Assessment</h3>{badge(obs["outcome"])}</div><p>{h(a["reason"])}</p><dl>'
        for key, value in a['evidence'].items():
            body += f'<dt>{h(key.replace("_", " ").title())}</dt><dd>{h(value)}</dd>'
        body += f'</dl><p><strong>Gateway summary</strong> <span class="mono">{h(obs["summary_id"])}</span></p><p><strong>Recording</strong> {h(obs["camera_name"])}<br><span class="mono">{h(obs["clip_start"])} → {h(obs["clip_end"])}</span></p>'
        body += details('Recording camera reference', obs['camera_id']) + details('Raw gateway response', obs['raw_response']) + details('Contract snapshot and exact prompt', obs['contract_json'])
        return body + '</article>'

    def request(self, request_id):
        j = self.op.request(request_id)
        m = j['metadata']
        body = f'<section><div class="section-heading"><h2>{h(m["contract"]["name"])}</h2>{badge(j["status"])}</div><p>{h(m["camera_name"])} · <span class="mono">{h(m["start"])} → {h(m["end"])}</span></p><p>{h(m["contract"]["expected_condition"])}</p>'
        body += details('Exact resulting prompt', m['payload']['Prompt']) + details('Exact inference request / recording reference', m['payload'])
        if j['message']:
            body += f'<p class="notice" role="status">{h(j["message"])}</p>'
        if j['summary_id']:
            body += f'<p>Gateway summary ID: <span class="mono">{h(j["summary_id"])}</span></p>'
        if j['status'] == 'preview':
            body += '<h3>2 / Explicit submission</h3><p>Submit spends one Hafnia inference. This request uses an inline prompt without the legacy rule-bound PromptId. The console stores a validated assessment and sends no native event.</p>'
            body += self.form('/submit', f'<input type="hidden" name="id" value="{h(request_id)}"><label class="check"><input type="checkbox" name="approved" value="yes" required>I approve one inference for this exact prompt and recording.</label><button>Submit one Hafnia inference</button>')
        if j['status'] in ('submitting', 'attention'):
            body += '<p class="notice">Never repeat a submission after an unknown result. Check gateway History and recover the original result. A server interruption can leave a request in this state.</p>'
        if j['summary_id'] and j['status'] != 'completed':
            body += self.form('/refresh', f'<input type="hidden" name="id" value="{h(request_id)}"><button>Refresh existing result (no inference)</button>')
            if j['status'] == 'running':
                body += '<p role="status">Waiting for the gateway. Checking every 5 seconds…</p><script src="/poll.js" defer></script>'
        if j['status'] in ('preview', 'attention', 'running'):
            body += '<h3>Use a previously recorded result</h3><p>Paste a saved terminal gateway JSON response or matching recovery manifest. Confirm the source recording metadata above against the original run. Responses without VideoUris do not establish their own provenance.</p>'
            body += self.form('/import', f'<input type="hidden" name="id" value="{h(request_id)}"><label>Saved response JSON<textarea name="result" rows="6" required></textarea></label><label class="check"><input type="checkbox" name="provenance" value="yes" required>I verified this result belongs to this exact contract, camera and UTC recording.</label><button class="secondary">Import evidence · no inference</button>')
        body += '</section>'
        if j['status'] == 'completed':
            row = self.op.store.db.execute('SELECT case_id FROM observations WHERE summary_id=?', (j['summary_id'],)).fetchone()
            case = self.op.store.case(row[0])
            obs = next(o for o in case['observations'] if o['summary_id'] == j['summary_id'])
            body += '<section>' + self.assessment(obs) + f'<a class="button" href="/cases/{case["id"]}">Open review case #{case["id"]}</a></section>'
        return self.page('Request & assessment', body, '/analyze')

    def case(self, case_id):
        c = self.op.store.case(case_id)
        latest = c['observations'][-1]
        body = f'<section><div class="section-heading"><h2>{h(latest["camera_name"])}</h2>{badge(c["state"])}</div><p>{h(latest["contract_json"]["expected_condition"])}</p><p>{h(latest["contract_json"]["operator_action"])}</p>'
        body += self.form('/review', f'<input type="hidden" name="id" value="{case_id}"><label>Operator review note<textarea name="note" maxlength="4000" rows="3" required></textarea></label><button>Mark reviewed with note</button>') + '</section>'
        body += '<section><h2>Native XProtect alarm information</h2><p>Only recorded checks and operator-confirmed associations are shown. Review state here does not acknowledge or close a native alarm.</p>'
        body += ''.join(f'<article>{badge(a["status"])}<p>Alarm ID: {h(a["alarm_id"] or "No confirmed association")}</p>{details("Candidate audit and operator verification", a["detail"])}</article>' for a in c['alarm_checks']) or '<p class="empty">No native alarm association has been recorded. This does not establish that an alarm is absent.</p>'
        body += '</section><section><h2>Evidence history</h2>' + ''.join(self.assessment(o) for o in reversed(c['observations'])) + '</section><section><h2>Review audit</h2>'
        body += ''.join(f'<p><time>{h(r["created_at"])}</time> · {h(r["kind"].replace("_", " "))}<br>{h(r["detail"])}</p>' for r in reversed(c['history']))
        return self.page(f'Review case #{case_id}', body + '</section>', '/')

    def post(self, path, f):
        if path == '/contracts':
            self.op.create_contract(f['name'], f['camera'], f['condition'])
            return '/contracts'
        if path == '/preview':
            return '/requests/' + self.op.preview(f['contract'], f['camera'], f['start'], f['end'])
        if path == '/review':
            if len(f['note']) > 4000:
                raise ValueError('Note too long')
            self.op.store.review(int(f['id']), f['note'])
            return '/cases/' + str(int(f['id']))
        request_id = f['id']
        if path == '/submit' and f.get('approved') == 'yes':
            self.op.submit(request_id)
        elif path == '/refresh':
            self.op.refresh(request_id)
        elif path == '/import' and f.get('provenance') == 'yes':
            self.op.import_result(request_id, json.loads(f['result']))
        else:
            raise ValueError('Unknown or unapproved action')
        return '/requests/' + request_id


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Camera names, summary IDs and request content stay out of access logs.

    def send(self, status, body, content_type='text/html; charset=utf-8'):
        data = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def handle_request(self):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send(403, 'Open the console using its printed 127.0.0.1 URL.')
            return
        store = Store(self.server.args.db)
        ui = Console(Operator(store, self.server.args.camera_map, self.server.args.contracts_dir), self.server.csrf)
        try:
            path = urlsplit(self.path).path
            if self.command == 'POST':
                if self.headers.get('Origin') not in (None, origin) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    self.send(403, 'Cross-origin action refused')
                    return
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024 * 1024 or self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    self.send(400, 'Invalid form body')
                    return
                values = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, max_num_fields=20)
                if any(len(v) != 1 for v in values.values()):
                    raise ValueError('Duplicate fields')
                f = {k: v[0] for k, v in values.items()}
                if not secrets.compare_digest(f.get('csrf', ''), self.server.csrf):
                    self.send(403, 'Invalid action token; reload the page')
                    return
                location = ui.post(path, f)
                self.send_response(303)
                self.send_header('Location', location)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', '0')
                self.end_headers()
            elif path in ('/style.css', '/poll.js'):
                self.send(200, (ASSETS / path[1:]).read_text(), 'text/css' if path.endswith('.css') else 'text/javascript')
            elif path == '/':
                self.send(200, ui.cases())
            elif path == '/contracts':
                self.send(200, ui.contracts())
            elif path == '/analyze':
                self.send(200, ui.analyze())
            elif path.startswith('/requests/'):
                self.send(200, ui.request(path.split('/')[-1]))
            elif path.startswith('/cases/'):
                self.send(200, ui.case(int(path.split('/')[-1])))
            else:
                self.send(404, ui.page('Page not found', '<p>Use the navigation to return to your workspace.</p>'))
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
            self.send(400, ui.page('Action needs attention', '<section><p>Input validation or storage failed. Check the selected camera, contract, UTC interval, JSON provenance and required fields. No inference is retried automatically.</p><a href="/">Return to review queue</a></section>'))
        finally:
            store.close()

    do_GET = handle_request
    do_POST = handle_request


def server(args):
    httpd = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    httpd.args, httpd.csrf = args, secrets.token_hex(32)
    return httpd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='runs/scene-contracts.sqlite3')
    parser.add_argument('--camera-map', default='cameras.local.json')
    parser.add_argument('--contracts-dir', default=str(DEFAULT_CONTRACTS))
    parser.add_argument('--port', type=int, default=8086)
    args = parser.parse_args()
    with server(args) as httpd:
        print(f'Scene Contracts: http://127.0.0.1:{httpd.server_port} (local VM browser only)', flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
