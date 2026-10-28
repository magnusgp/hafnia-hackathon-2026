"""Preview or send ONE uniquely keyed test Analytics Event for the Smart Client camera-preview investigation.

Preview is the default and sends nothing. A send needs --approve with the first 12+ hex digits of the previewed
SHA-256, goes through the shared claim-before-POST ledger (existing rows are never touched) and never retries.
The camera, management server and event name come from the caller; nothing is invented.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scene_contracts.analytics_event import Ledger, build, send

EVENT = 'Adaptive Watch Review Required'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera-id', required=True)
    p.add_argument('--tag', required=True, help='unique label, e.g. preview-test-1; becomes the dispatch key')
    p.add_argument('--seconds-ago', type=int, default=120, help='source time, inside the retained recording')
    p.add_argument('--at', help='fixed source time (UTC ISO) so preview and send hash the same bytes')
    p.add_argument('--server-id'); p.add_argument('--server-type', default='XPCO')
    p.add_argument('--server-host'); p.add_argument('--server-port', type=int)
    p.add_argument('--target', default='127.0.0.1:9090')
    p.add_argument('--ledger', type=Path, default=Path('runs/release/native/ledger.sqlite3'))
    p.add_argument('--approve')
    a = p.parse_args()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    at = datetime.fromisoformat(a.at.replace('Z', '+00:00')) if a.at else now - timedelta(seconds=a.seconds_ago)
    key = 'sc1-test-' + a.tag
    server = dict(type=a.server_type, hostname=a.server_host, port=a.server_port, id=a.server_id) if a.server_id else None
    xml = build(EVENT, a.camera_id, at, key, description=f'INTEGRATION TEST {a.tag}: Smart Client preview check, not a real review exception.',
                start=at - timedelta(seconds=5), end=at + timedelta(seconds=5), server_id=server, vendor='Adaptive Watch')
    digest = hashlib.sha256(xml).hexdigest()
    print(xml.decode()); print('sha256', digest, 'key', key, 'target', a.target)
    if not a.approve:
        print('PREVIEW ONLY. Nothing sent.'); return
    ledger = Ledger(a.ledger)
    try:
        row = send(ledger, key, xml, a.target, a.approve)
    finally:
        ledger.close()
    print('state', row['state'], 'http', row['http_status'], 'response', repr(row['response']))


if __name__ == '__main__':
    main()
