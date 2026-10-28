"""Private, fail-closed controlled evaluation; sequential concurrency = one.

Quota contract must be verified from the installed gateway documentation first.
No PromptId, event, alarm or dispatch endpoints are used.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import getpass
import json
from pathlib import Path
import sqlite3
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from adaptive_watch.evaluation import parse_result
from scene_contracts.gateway import Gateway, video_uri

TERMINAL = {'valid_model_decision','gateway_inference_failure','empty_response','malformed_format','valid_descriptive_response'}


def parse_descriptive(item):
    """Keep literal diagnostic prose; semantic review is a separate operation."""
    if item.get('Progress') != 'Completed':
        return dict(category='gateway_inference_failure' if item.get('Progress') == 'Failed' else 'pending',
                    analysis_success=False, parser_version='diagnostic-text-1')
    text = item.get('Response')
    category = ('empty_response' if text is None or isinstance(text,str) and not text.strip()
                else 'valid_descriptive_response' if isinstance(text,str) else 'malformed_format')
    return dict(category=category, analysis_success=True, parser_version='diagnostic-text-1',
                literal_response=text, semantic_review='pending', outcome=None)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Runner:
    def __init__(self, root, cap=480, descriptive=False):
        if not 1 <= cap <= 480:
            raise ValueError('Daily cap must be 1..480; preserve gateway headroom')
        self.root, self.cap = Path(root), cap
        self.descriptive = descriptive
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'reliability-ledger.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests (experiment TEXT PRIMARY KEY, day TEXT, stage TEXT, payload TEXT, state TEXT, summary_id TEXT, result TEXT)')
        self.db.commit()

    def reserve(self, entry, payload, remaining):
        if type(remaining) is not int or not 0 <= remaining <= 500:
            raise ValueError('Invalid live quota balance')
        day = datetime.now(timezone.utc).date().isoformat()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT 1 FROM requests WHERE state=?', ('ambiguous',)).fetchone():
                raise ValueError('Reconcile ambiguous requests before new submissions')
            if any(row[0] not in TERMINAL for row in self.db.execute('SELECT state FROM requests')):
                raise ValueError('Existing request remains in flight; resume its summary ID first')
            used = self.db.execute('SELECT COUNT(*) FROM requests WHERE day=?', (day,)).fetchone()[0]
            if used >= self.cap or remaining <= 20:
                raise ValueError('Daily cap or gateway headroom reached')
            limit = {'A':128, 'B':192, 'C':144}[entry['stage']]
            count = self.db.execute('SELECT COUNT(*) FROM requests WHERE stage=?', (entry['stage'],)).fetchone()[0]
            if count >= limit:
                raise ValueError('Stage cap reached')
            self.db.execute('INSERT INTO requests VALUES (?,?,?,?,?,NULL,NULL)',
                (entry['experiment_id'], day, entry['stage'], json.dumps(payload, sort_keys=True), 'ambiguous'))

    def reconcile(self, gateway, experiment, summary_id):
        validate_summary_id(summary_id)
        row = self.db.execute('SELECT payload,summary_id FROM requests WHERE experiment=?', (experiment,)).fetchone()
        if not row or row[1] and row[1] != summary_id:
            raise ValueError('Unknown experiment or conflicting summary ID')
        result = gateway.request('GET', '/api/Summaries/' + summary_id)
        expected = json.loads(row[0])
        returned = result.get('Request') if isinstance(result, dict) else None
        if (not isinstance(returned, dict) or result.get('Id') != summary_id
                or any(returned.get(k) != v for k,v in expected.items())):
            raise ValueError('Reconciliation requires exact returned prompt and video URI; retain ambiguity otherwise')
        with self.db:
            self.db.execute('UPDATE requests SET summary_id=?,state=? WHERE experiment=?', (summary_id, 'submitted', experiment))

    def poll(self, gateway, experiment, summary_id):
        validate_summary_id(summary_id)
        row = self.db.execute('SELECT summary_id FROM requests WHERE experiment=?', (experiment,)).fetchone()
        if not row or row[0] != summary_id:
            raise ValueError('Summary ID is not bound to this experiment')
        result = gateway.request('GET', '/api/Summaries/' + summary_id)
        if not isinstance(result, dict) or result.get('Id') != summary_id:
            raise ValueError('Unexpected summary identity; retain pending reservation')
        parsed = parse_descriptive(result) if self.descriptive else parse_result(result)
        with self.db:
            self.db.execute('UPDATE requests SET state=?,result=? WHERE experiment=?',
                (parsed['category'], json.dumps(dict(raw=result, parsed=parsed)), experiment))
        return parsed['category']


def validate_summary_id(value):
    if not isinstance(value, str) or not value or any(c not in '0123456789abcdefABCDEF-' for c in value):
        raise ValueError('Invalid summary ID')


def await_summary(runner, gateway, experiment, summary_id, timeout=60):
    """Resume one ID to a terminal state before allowing another reservation."""
    deadline = time.monotonic() + timeout
    while True:
        category = runner.poll(gateway, experiment, summary_id)
        print(experiment, category)
        if category in TERMINAL:
            return category
        if time.monotonic() >= deadline:
            raise TimeoutError('Existing summary remains pending; rerun this plan to resume its ID')
        time.sleep(3)


def validate_age(entry, now=None):
    now = now or datetime.now(timezone.utc)
    start,end = [datetime.fromisoformat(entry[k].replace('Z','+00:00')) for k in ('start','end')]
    if start.tzinfo is None or end.tzinfo is None or not now-timedelta(hours=24) < start < end <= now:
        raise ValueError('Recording must be in the past and less than 24 hours old')


def validate(plan, review):
    human = review.get('status') == 'human_confirmed'
    demo = (review.get('status') == 'reviewed' and review.get('review_mode') == 'ai_demo'
            and review.get('user_authorized_ai_review') is True)
    if not (human or demo) or not review.get('reviewer') or not review.get('reviewed_at'):
        raise ValueError('Phase A human review or explicitly authorized AI demo review is required')
    definitions = REPO / 'docs/research/reliability/label-definitions.json'
    if review.get('definitions_sha256') != hashlib.sha256(definitions.read_bytes()).hexdigest():
        raise ValueError('Review must bind frozen definitions')
    draft = Path(review['review_artifact'])
    if review.get('review_artifact_sha256') != hashlib.sha256(draft.read_bytes()).hexdigest():
        raise ValueError('Human review must bind the timestamped source labels')
    reviewed_sources = json.loads(draft.read_text(encoding='utf-8-sig')).get('sources', [])
    ids = set()
    for e in plan:
        if e['experiment_id'] in ids or e['stage'] not in {'A','B','C'}:
            raise ValueError('Duplicate experiment or invalid stage')
        ids.add(e['experiment_id'])
        allowed_continuity = {'human_confirmed_no_loop_boundary'}
        if demo:
            allowed_continuity.add('ai_reviewed_no_loop_boundary')
        if not e.get('event_id') or not e.get('prompt') or e.get('continuity_review') not in allowed_continuity:
            raise ValueError('Event identity, exact prompt and reviewed continuity required')
        if e.get('label_review_sha256') != review['review_artifact_sha256']:
            raise ValueError('Every experiment must bind the reviewed source artifact')
        start,end = [datetime.fromisoformat(e[k].replace('Z','+00:00')) for k in ('start','end')]
        validate_age(e)
        if start.tzinfo is None or end.tzinfo is None or not 12 <= (end-start).total_seconds() <= 17:
            raise ValueError('Only existing 12–17 second interval contract supported; short intervals unverified')
        if start.microsecond or end.microsecond:
            raise ValueError('Gateway URIs use whole seconds; fractional boundaries cannot be silently rounded')
        manifest = Path(e['recording_manifest'])
        if hashlib.sha256(manifest.read_bytes()).hexdigest() != e['manifest_sha256']:
            raise ValueError('Manifest hash mismatch')
        m = json.loads(manifest.read_text(encoding='utf-8-sig'))
        reviewed = next((s for s in reviewed_sources if s['event_id'] == e['event_id']
                         and s['manifest_sha256'] == e['manifest_sha256']), None)
        if not reviewed:
            raise ValueError('Experiment source is absent from frozen review')
        reviewed_frames = {f['timestamp_utc']:f for f in reviewed['frames']}
        if not m.get('frames'):
            raise ValueError('Hash-bound recorded frames required')
        ms,me = [datetime.fromisoformat(m[k].replace('Z','+00:00')) for k in ('requested_start_utc','requested_end_utc')]
        if m['camera_id'].lower() != e['camera_id'].lower() or not ms <= start < end <= me:
            raise ValueError('Recording provenance mismatch')
        export = m.get('mkv_export')
        if export:
            video = (manifest.parent/export['file']).resolve()
            if (not video.is_relative_to(manifest.parent.resolve())
                    or hashlib.sha256(video.read_bytes()).hexdigest() != export['sha256']
                    or reviewed.get('video_sha256',export['sha256']) != export['sha256']):
                raise ValueError('Original video export path or hash mismatch')
        sequences = m.get('recording_sequences')
        if sequences and not any(datetime.fromisoformat(s['start_utc'].replace('Z','+00:00')) <= start < end
                <= datetime.fromisoformat(s['end_utc'].replace('Z','+00:00')) for s in sequences):
            raise ValueError('Recording sequence does not cover request')
        for frame in m['frames']:
            source = (manifest.parent / frame['file']).resolve()
            annotation = reviewed_frames.get(frame['timestamp_utc'], {})
            expected = annotation.get('sha256')
            if (not source.is_relative_to(manifest.parent.resolve()) or not expected
                    or hashlib.sha256(source.read_bytes()).hexdigest() != expected
                    or frame.get('sha256',expected) != expected):
                raise ValueError('Recording frame path or hash mismatch')
        yield e, dict(Prompt=e['prompt'], VideoUris=[video_uri(e['camera_id'],start,end)])


def operator_authenticate(gateway):
    """Operator terminal only; never consume possibly stale password environment."""
    if not sys.stdin.isatty():
        raise ValueError('Run in a user-opened terminal after confirming gateway authentication')
    password = getpass.getpass('Gateway administrator password: ')
    response = gateway.request('POST','/api/Sessions/Login',
                               dict(Name='administrator',Password=password),login=True)
    gateway.session = response.get('Id') if isinstance(response,dict) else None
    if not gateway.session:
        raise ValueError('Gateway returned no session ID')


def verify_availability(entry, evidence, now=None):
    """Require recent operator recording-coverage evidence, separate from labels."""
    now = now or datetime.now(timezone.utc)
    match = next((v for v in evidence.get('recordings',[]) if v.get('event_id') == entry['event_id']
                  and v.get('manifest_sha256') == entry['manifest_sha256']), None)
    if not match or match.get('available') is not True or not match.get('checked_by'):
        raise ValueError('Exact source recording availability is unverified; never substitute later loops')
    checked = datetime.fromisoformat(match['checked_at'].replace('Z','+00:00'))
    if checked.tzinfo is None or not 0 <= (now-checked).total_seconds() <= 900:
        raise ValueError('Recording availability evidence must be from the last 15 minutes')
    start,end = [datetime.fromisoformat(entry[k].replace('Z','+00:00')) for k in ('start','end')]
    lo,hi = [datetime.fromisoformat(match[k].replace('Z','+00:00')) for k in ('coverage_start','coverage_end')]
    if not lo <= start < end <= hi:
        raise ValueError('Verified recording coverage does not contain requested interval')
    proof = Path(match['evidence_file'])
    if hashlib.sha256(proof.read_bytes()).hexdigest() != match['evidence_sha256']:
        raise ValueError('Recording availability evidence hash mismatch')


def quota_balance(raw, contract, now=None):
    now=now or datetime.now(timezone.utc)
    if contract.get('kind')=='gateway_system_information':
        if contract.get('endpoint')!='/api/System/Information':
            raise ValueError('Unexpected installed quota endpoint')
        q=raw['QuotaInformation']
        limit,used=q['DailySummaryQuota'],q['DailySummaryCount']
        if type(limit) is not int or limit!=500 or type(used) is not int or not 0<=used<=limit:
            raise ValueError('Quota schema/cap mismatch')
        reset=datetime.fromisoformat(q['DailySummaryReset'].replace('Z','+00:00'))
        if reset.tzinfo is None or not now<reset<=now+timedelta(days=1):
            raise ValueError('Quota reset is stale or unverified')
        return limit-used
    remaining=raw[contract['remaining_field']]
    if (raw[contract['day_field']]!=now.date().isoformat() or raw[contract['limit_field']]!=500
            or type(remaining) is not int or not 0<=remaining<=500):
        raise ValueError('Quota schema/date/cap mismatch')
    return remaining


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True, help='One durable private root for all days and stages')
    p.add_argument('--plan', type=Path)
    p.add_argument('--review', type=Path)
    p.add_argument('--quota-contract', type=Path, help='Verified read-only endpoint and remaining/limit/day field names')
    p.add_argument('--daily-cap', type=int, default=480)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--authenticated-preflight', action='store_true', help='Validate plan, log in once and perform read-only history query; never submit summaries')
    p.add_argument('--operator-auth-confirmed', action='store_true', help='Operator has independently confirmed authentication; required for any login')
    p.add_argument('--recording-availability', type=Path, help='Recent hash-bound operator check of exact original recording coverage')
    p.add_argument('--reconcile', nargs=2, metavar=('EXPERIMENT','SUMMARY_ID'))
    a = p.parse_args()
    if a.apply and a.authenticated_preflight:
        p.error('Authenticated preflight and submission are separate modes')
    if a.root.resolve().is_relative_to(REPO) and not a.root.resolve().is_relative_to(REPO / 'runs'):
        p.error('Raw outputs must be outside Git or under ignored runs/')
    runner = Runner(a.root, a.daily_cap)
    if a.reconcile:
        if not a.operator_auth_confirmed:
            p.error('Confirm authentication in the operator terminal first; no login attempted')
        g = Gateway(); operator_authenticate(g)
        runner.reconcile(g, *a.reconcile)
        return
    if not a.plan or not a.review:
        p.error('--plan and --review required')
    plan = json.loads(a.plan.read_text())
    prepared = list(validate(plan, json.loads(a.review.read_text())))
    frozen = a.root / 'plan.sha256'
    value = digest(plan)
    if frozen.exists() and frozen.read_text() != value:
        raise ValueError('Plan differs from frozen plan; do not replace ledger root to retry')
    archived = a.root/'plan.private.json'
    if archived.exists() and digest(json.loads(archived.read_text())) != value:
        raise ValueError('Archived source/ground-truth plan changed')
    if not archived.exists():
        archived.write_text(json.dumps(plan,indent=2))
    frozen.write_text(value)
    print('Validated', len(prepared), 'experiments; concurrency=1')
    if not a.apply and not a.authenticated_preflight:
        runner.db.close()
        return
    if not a.operator_auth_confirmed:
        p.error('Confirm authentication in the operator terminal first; no login attempted')
    if a.authenticated_preflight:
        g = Gateway(); operator_authenticate(g)
        history = g.request('GET','/api/Summaries?Limit=1')
        if not isinstance(history,(dict,list)):
            raise ValueError('Authenticated history query returned an unexpected shape')
        proof = dict(success=True,checked_at=datetime.now(timezone.utc).isoformat(),
                     plan_sha256=value,authenticated_read='GET /api/Summaries?Limit=1',new_summaries=0)
        (a.root/'authenticated-preflight.json').write_text(json.dumps(proof,indent=2))
        print('Authenticated preflight passed; zero summary submissions')
        # Installed gateway client documents this GET; retain quota fields only.
        try:
            info=g.request('GET','/api/System/Information')
            q=info['QuotaInformation']
            (a.root/'quota-preflight.private.json').write_text(json.dumps(dict(
                checked_at=datetime.now(timezone.utc).isoformat(),plan_sha256=value,QuotaInformation=q),indent=2))
            print('Read-only quota snapshot saved privately')
        except Exception as exc:
            print('Quota snapshot unavailable:',type(exc).__name__)
        runner.db.close()
        return
    proof_path = a.root/'authenticated-preflight.json'
    if not proof_path.exists():
        p.error('Successful authenticated preflight required before submission')
    proof = json.loads(proof_path.read_text())
    if proof.get('success') is not True or proof.get('plan_sha256') != value:
        p.error('Authenticated preflight does not bind this plan')
    if not a.quota_contract:
        p.error('Verified live quota contract required; no guessed endpoint or quota')
    contract = json.loads(a.quota_contract.read_text())
    endpoint = contract['endpoint']
    if not endpoint.startswith('/api/') or '?' in endpoint or not contract.get('verified_from'):
        raise ValueError('Verified read-only quota endpoint required')
    availability = json.loads(a.recording_availability.read_text(encoding='utf-8-sig')) if a.recording_availability else {}
    for e,_ in prepared:
        if not runner.db.execute('SELECT 1 FROM requests WHERE experiment=?',(e['experiment_id'],)).fetchone():
            verify_availability(e,availability)
    g = Gateway(); operator_authenticate(g)
    for e,payload in prepared:
        old = runner.db.execute('SELECT summary_id,state,payload FROM requests WHERE experiment=?', (e['experiment_id'],)).fetchone()
        if old:
            if json.loads(old[2]) != payload:
                raise ValueError('Experiment payload changed')
            if not old[0]:
                raise ValueError('Ambiguous submission; reconcile exact summary ID, never resubmit')
            if old[1] not in TERMINAL:
                await_summary(runner,g,e['experiment_id'],old[0])
            continue
        quota = g.request('GET', endpoint)
        validate_age(e)
        verify_availability(e,availability)
        remaining = quota_balance(quota,contract)
        (a.root / 'quota-latest.private.json').write_text(json.dumps(quota))
        runner.reserve(e,payload,remaining)
        # Claim committed before POST. Any exception leaves an ambiguous reservation.
        result = g.request('POST', '/api/Summaries', payload)
        if not isinstance(result,dict) or not result.get('Id'):
            raise ValueError('Ambiguous submission; reconcile, never retry')
        validate_summary_id(result['Id'])
        with runner.db:
            runner.db.execute('UPDATE requests SET summary_id=?,state=? WHERE experiment=?', (result['Id'],'submitted',e['experiment_id']))
        await_summary(runner,g,e['experiment_id'],result['Id'])


if __name__ == '__main__':
    main()
