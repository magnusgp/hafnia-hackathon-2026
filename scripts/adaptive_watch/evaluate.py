"""Preview a private evaluation plan; --apply sends at most 16 sequential requests.

Authentication uses HAFNIA_GW_PASSWORD or an interactive hidden local password prompt.
No PromptId, event generation, retry, or VMS configuration operations exist here.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adaptive_watch.evaluation import Evaluation, prompt
from scene_contracts.gateway import Gateway

p = argparse.ArgumentParser()
p.add_argument('plan',type=Path)
p.add_argument('--root',type=Path,default=Path('runs/hybrid/evaluation'))
p.add_argument('--apply',action='store_true')
a = p.parse_args()
entries = json.loads(a.plan.read_text(encoding='utf-8-sig'))
if not 1 <= len(entries) <= 16:
    p.error('A batch must contain 1–16 controlled requests')
for entry in entries:
    print(json.dumps(dict(entry=entry,prompt=prompt(entry['scene'],entry['prompt_version']))))
if a.apply:
    gateway = Gateway()
    quota = gateway.request('GET','/api/System/Information')['QuotaInformation']
    if quota['DailySummaryCount']+len(entries)>quota['DailySummaryQuota']:
        p.error('Insufficient daily quota')
    gateway.authenticate()
    evaluation = Evaluation(a.root)
    for entry in entries:
        digest, record = evaluation.submit(gateway,entry)
        print('Submitted',record['summary']['Id'],flush=True)
        record = evaluation.poll(gateway,digest,record)
        print(json.dumps(record['parsed']),flush=True)
