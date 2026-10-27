"""Execute only the operator-authorized frozen REL26-D matrix; no extra calls."""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from reliability_runner import (Runner, Gateway, REPO, validate, validate_age,
    verify_availability, quota_balance, operator_authenticate, digest,
    validate_summary_id, await_summary, TERMINAL)


def main():
    root = REPO/'runs/reliability-diagnostics'
    matrix_path = REPO/'docs/reliability/diagnostic-24-matrix.json'
    matrix = json.loads(matrix_path.read_text(encoding='utf-8-sig'))
    plan = json.loads((root/'execution-plan-v1.private.json').read_text(encoding='utf-8-sig'))
    review = json.loads((root/'signoff-v1.private.json').read_text(encoding='utf-8-sig'))
    prepared = list(validate(plan, review))
    if len(plan) != 24 or len(matrix['experiments']) != 24:
        raise ValueError('Exactly 24 definitions required')
    matrix_hash = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    for entry, definition in zip(plan, matrix['experiments']):
        for key in ('experiment_id','prompt','prompt_sha256','scene','family','repeat'):
            if entry[key] != definition[key]:
                raise ValueError('Frozen matrix mismatch')
        if (hashlib.sha256(entry['prompt'].encode()).hexdigest() != entry['prompt_sha256']
                or entry['original_matrix_sha256'] != matrix_hash
                or entry['response_contract'] != 'diagnostic_free_text'):
            raise ValueError('Prompt/source binding mismatch')
    runner = Runner(root/'operator-batch', descriptive=True)
    try:
        execute(root,plan,prepared,runner)
    finally:
        runner.db.close()


def execute(root,plan,prepared,runner):
    plan_hash = digest(plan)
    frozen = runner.root/'plan.sha256'
    if frozen.exists() and frozen.read_text() != plan_hash:
        raise ValueError('Ledger plan changed')
    frozen.write_text(plan_hash)
    archive = runner.root/'plan.private.json'
    if archive.exists() and digest(json.loads(archive.read_text())) != plan_hash:
        raise ValueError('Archived plan changed')
    if not archive.exists():
        archive.write_text(json.dumps(plan,indent=2))
    ids = {entry['experiment_id'] for entry in plan}
    if any(row[0] not in ids for row in runner.db.execute('SELECT experiment FROM requests')):
        raise ValueError('Unexpected ledger claim')
    availability = json.loads((root/'recording-availability.private.json').read_text(encoding='utf-8-sig'))
    remaining_entries = [e for e,_ in prepared if not runner.db.execute(
        'SELECT 1 FROM requests WHERE experiment=?',(e['experiment_id'],)).fetchone()]
    for entry in remaining_entries:
        verify_availability(entry,availability)
    print('Validated 24 frozen experiments; concurrency=1; diagnostic prose preserved',flush=True)
    gateway = Gateway()
    operator_authenticate(gateway)  # One login, local terminal only; no environment password.
    history = gateway.request('GET','/api/Summaries?Limit=1')
    if not isinstance(history,(dict,list)):
        raise ValueError('Authenticated inference-history check failed')
    contract = json.loads((REPO/'docs/reliability/quota-contract.json').read_text())
    quota = gateway.request('GET',contract['endpoint'])
    balance = quota_balance(quota,contract)
    today = datetime.now(timezone.utc).date().isoformat()
    used = runner.db.execute('SELECT COUNT(*) FROM requests WHERE day=?',(today,)).fetchone()[0]
    if balance-len(remaining_entries) < 20 or used+len(remaining_entries) > runner.cap:
        raise ValueError('Insufficient quota for entire remaining campaign')
    (runner.root/'execution-preflight.private.json').write_text(json.dumps(dict(
        checked_at=datetime.now(timezone.utc).isoformat(),plan_sha256=plan_hash,
        authentication='successful_history_read',remaining=balance,new_requests=len(remaining_entries),
        QuotaInformation=quota['QuotaInformation']),indent=2))
    print('Authenticated preflight passed; quota sufficient for remaining authorized requests',flush=True)
    for entry,payload in prepared:
        experiment = entry['experiment_id']
        old = runner.db.execute('SELECT summary_id,state,payload FROM requests WHERE experiment=?',(experiment,)).fetchone()
        if old:
            if json.loads(old[2]) != payload:
                raise ValueError('Existing payload differs')
            if not old[0]:
                raise ValueError('Ambiguous claim: reconcile summary ID before continuing; never retry')
            if old[1] not in TERMINAL:
                await_summary(runner,gateway,experiment,old[0])
            continue
        validate_age(entry)
        verify_availability(entry,availability)
        quota = gateway.request('GET',contract['endpoint'])
        balance = quota_balance(quota,contract)
        validate_age(entry)
        verify_availability(entry,availability)
        runner.reserve(entry,payload,balance)
        response = gateway.request('POST','/api/Summaries',payload)
        # Archive every successful POST envelope before polling. Claim survives exceptions.
        (runner.root/(experiment+'.submission.private.json')).write_text(json.dumps(response,indent=2))
        if not isinstance(response,dict) or not response.get('Id'):
            raise ValueError('Ambiguous POST: reconcile, never retry')
        validate_summary_id(response['Id'])
        with runner.db:
            runner.db.execute('UPDATE requests SET summary_id=?,state=? WHERE experiment=?',
                              (response['Id'],'submitted',experiment))
        await_summary(runner,gateway,experiment,response['Id'])
    print('Authorized campaign finished; no further inference will be submitted',flush=True)


if __name__ == '__main__':
    main()
