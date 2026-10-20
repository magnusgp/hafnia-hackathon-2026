"""Scene Contracts CLI. Offline ingestion never invokes Hafnia."""
import argparse
import hashlib
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from uuid import UUID
from urllib.parse import quote

from scene_contracts.contracts import DEFAULT_CONTRACTS, load_contracts
from scene_contracts.gateway import Gateway, GatewayError, video_uri
from scene_contracts.store import Store, interval
from scene_contracts.xprotect import XProtect, XProtectError, associate


def show(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def camera(args, contract):
    if args.camera not in contract['camera_names']:
        raise ValueError('Camera name is not selected by this contract')
    if args.camera_map:
        rows = json.loads(Path(args.camera_map).read_text(encoding='utf-8-sig'))
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError('Camera map must contain Name/Id records')
        matches = [r for r in rows if r.get('Name') == args.camera]
        if len(matches) != 1:
            raise ValueError('Camera name must resolve to exactly one camera')
        found = str(UUID(matches[0]['Id']))
        if args.camera_id and str(UUID(args.camera_id)) != found:
            raise ValueError('Camera ID conflicts with name catalog')
        return found
    if not args.camera_id:
        raise ValueError('Provide --camera-map or an explicitly verified --camera-id')
    return str(UUID(args.camera_id))


def evaluate(args, contract, camera_id, start, end):
    uri = video_uri(camera_id, datetime.fromisoformat(start.replace('Z', '+00:00')), datetime.fromisoformat(end.replace('Z', '+00:00')))
    show({'contract': contract['id'], 'version': contract['version'], 'camera': args.camera,
          'video_uri': uri, 'prompt': contract['assessment_prompt'], 'apply': args.apply})
    if not args.apply:
        print('DRY RUN: no network access or VLM call. Add --apply to submit once; the existing gateway rule may create an alarm.')
        return None
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    client = Gateway()
    client.authenticate()
    title = contract.get('gateway_prompt_title')
    prompt = client.exact_item('Prompts', 'Title', title) if title else None
    if title and (not prompt or prompt.get('Text', '').strip() != contract['assessment_prompt'].strip()):
        raise ValueError('Saved gateway prompt missing or differs from contract; no inference submitted')
    payload = {'Prompt': contract['assessment_prompt'], 'VideoUris': [uri]}
    if prompt:
        payload['PromptId'] = prompt['Id']
    item = client.request('POST', '/api/Summaries', payload)
    if not isinstance(item, dict) or not isinstance(item.get('Id'), str) or not item['Id']:
        raise GatewayError('Submission returned no summary ID; do not retry automatically')
    sid = item['Id']
    print('Submitted summary ID:', sid)
    target = output / ('summary-' + hashlib.sha256(sid.encode()).hexdigest() + '.json')
    manifest = {'camera_id': camera_id, 'camera_name': args.camera, 'start': start, 'end': end, 'contract': contract}

    def save():
        manifest['result'] = {k: item.get(k) for k in ('Id', 'Progress', 'Response')}
        pending = target.with_suffix('.tmp')
        pending.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        pending.replace(target)

    save()
    deadline = time.monotonic() + args.max_wait
    while item.get('Progress') not in {'Completed', 'Failed'} and time.monotonic() < deadline:
        time.sleep(3)
        item = client.request('GET', '/api/Summaries/' + quote(sid, safe=''))
        if not isinstance(item, dict) or item.get('Id') != sid:
            raise GatewayError('Unexpected summary identity; original submission is in the manifest')
        save()
    print('Saved recovery manifest:', target)
    if item.get('Progress') not in {'Completed', 'Failed'}:
        print('Still pending. Fetch this summary later with ingest --summary-id; do not resubmit.')
        return None
    return item


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default='runs/scene-contracts.sqlite3')
    p.add_argument('--contracts-dir', default=str(DEFAULT_CONTRACTS))
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('contracts')
    for name in ('evaluate', 'ingest'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--contract', required=True)
        cmd.add_argument('--camera', required=True, help='Exact camera name in the contract')
        cmd.add_argument('--camera-map', help='Local JSON export of Get-VmsCamera Name/Id')
        cmd.add_argument('--camera-id', help='Fallback verified GUID; prefer --camera-map')
        cmd.add_argument('--start', required=True)
        cmd.add_argument('--end', required=True)
        if name == 'evaluate':
            cmd.add_argument('--apply', action='store_true')
            cmd.add_argument('--max-wait', type=int, default=600)
            cmd.add_argument('--output-dir', default='runs')
        else:
            source = cmd.add_mutually_exclusive_group(required=True)
            source.add_argument('--file', help='Raw v0.1 result or v0.2 recovery manifest')
            source.add_argument('--summary-id', help='Fetch existing summary (GET only, no VLM call)')
    sub.add_parser('cases')
    detail = sub.add_parser('case')
    detail.add_argument('id', type=int)
    review = sub.add_parser('review')
    review.add_argument('id', type=int)
    review.add_argument('--note', required=True)
    for name in ('alarms', 'events', 'associate'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--xprotect-url', default=os.getenv('XPROTECT_URL'))
        cmd.add_argument('--ca-file', default=os.getenv('XPROTECT_CA_FILE'))
        cmd.add_argument('--start', required=True, help='Alarm/event trigger UTC, usually inference time, not clip time')
        cmd.add_argument('--end', required=True)
        if name == 'associate':
            cmd.add_argument('--case-id', type=int, required=True)
            cmd.add_argument('--alarm-name', required=True)
            cmd.add_argument('--alarm-id', help='Explicit operator-confirmed alarm GUID')
            cmd.add_argument('--note')
    return p


def run(args):
    if args.command == 'contracts':
        show(load_contracts(args.contracts_dir))
        return
    if args.command in {'alarms', 'events', 'associate'}:
        start, end = interval(args.start, args.end)
        if not args.xprotect_url:
            raise ValueError('Set XPROTECT_URL to the actual HTTPS XProtect API Gateway origin')
        client = XProtect(args.xprotect_url, args.ca_file)
        client.authenticate()
        if args.command != 'associate':
            show(client.collection(args.command, start, end))
            return
        store = Store(args.db)
        try:
            show(associate(store, client, args.case_id, start, end, args.alarm_name, args.alarm_id, args.note))
        finally:
            store.close()
        return
    if args.command in {'evaluate', 'ingest'}:
        matches = [c for c in load_contracts(args.contracts_dir) if c['id'] == args.contract]
        if len(matches) != 1:
            raise ValueError('Unknown contract ID')
        contract = matches[0]
        camera_id = camera(args, contract)
        start, end = interval(args.start, args.end)
        if args.command == 'evaluate':
            if args.max_wait <= 0:
                raise ValueError('--max-wait must be positive')
            item = evaluate(args, contract, camera_id, start, end)
            if item is None:
                return
        elif args.file:
            item = json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
            if isinstance(item, dict) and 'result' in item:
                if (item.get('camera_id'), item.get('camera_name'), item.get('start'), item.get('end'), item.get('contract')) != (camera_id, args.camera, start, end, contract):
                    raise ValueError('Manifest provenance conflicts with selected interval/contract')
                item = item['result']
        else:
            client = Gateway()
            client.authenticate()
            item = client.request('GET', '/api/Summaries/' + quote(args.summary_id, safe=''))
            if not isinstance(item, dict) or item.get('Id') != args.summary_id:
                raise ValueError('Retrieved summary ID does not match requested summary')
        if not isinstance(item, dict):
            raise ValueError('Gateway result must be an object')
        if 'VideoUris' in item:
            expected = video_uri(camera_id, datetime.fromisoformat(start.replace('Z', '+00:00')), datetime.fromisoformat(end.replace('Z', '+00:00')))
            if item['VideoUris'] != [expected]:
                raise ValueError('Gateway video provenance conflicts with selected interval')
    store = Store(args.db)
    try:
        if args.command in {'evaluate', 'ingest'}:
            observation, created = store.ingest(contract, item, camera_id, args.camera, start, end)
            show({'created': created, 'observation': observation})
        elif args.command == 'cases':
            show(store.cases())
        elif args.command == 'case':
            show(store.case(args.id))
        elif args.command == 'review':
            store.review(args.id, args.note)
            show(store.case(args.id))
    finally:
        store.close()


def main():
    args = parser().parse_args()
    try:
        run(args)
    except (GatewayError, XProtectError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError):
        # Do not echo arbitrary server/file content, URLs, credentials or bearer tokens.
        print('ERROR: operation failed validation, persistence or API access. Check inputs, API availability and permissions; never automatically resubmit inference.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
