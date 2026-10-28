"""Offline full-campaign cap, resume and preflight tests. No network."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
import reliability_diagnostic_execute as campaign


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        directory = self.root/'docs/research/reliability'
        directory.mkdir(parents=True)
        for name in ('diagnostic-24-matrix.json','quota-contract.json'):
            (directory/name).write_bytes((REPO/'docs/research/reliability'/name).read_bytes())
        matrix = json.loads((directory/'diagnostic-24-matrix.json').read_text())
        matrix_hash=hashlib.sha256((directory/'diagnostic-24-matrix.json').read_bytes()).hexdigest()
        self.plan=[dict(row,stage='B',original_matrix_sha256=matrix_hash,response_contract='diagnostic_free_text')
                   for row in matrix['experiments']]
        self.private=self.root/'runs/reliability-diagnostics'
        self.private.mkdir(parents=True)
        for name,data in [('execution-plan-v1.private.json',self.plan),('signoff-v1.private.json',{}),
                          ('recording-availability.private.json',{})]:
            (self.private/name).write_text(json.dumps(data))
        self.posts=[]
        outer=self
        class Gateway:
            def request(inner,method,path,payload=None):
                if path == '/api/System/Information':
                    return dict(QuotaInformation=dict(DailySummaryQuota=500,DailySummaryCount=len(outer.posts),
                        DailySummaryReset=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
                if path == '/api/Summaries?Limit=1': return []
                if method == 'POST':
                    outer.posts.append(payload)
                    return dict(Id=f'{len(outer.posts):08x}')
                index=int(path.rsplit('/',1)[1],16)-1
                return dict(Id=f'{index+1:08x}',Progress='Completed',Response='Visible person.',
                            Request=dict(**outer.posts[index],AiModelId='traffic-general'))
        self.gateway=Gateway()

    def tearDown(self):
        self.tmp.cleanup()

    def run_campaign(self):
        prepared=[(e,dict(Prompt=e['prompt'],VideoUris=['private-source-'+e['scene']])) for e in self.plan]
        with patch.object(campaign,'REPO',self.root),patch.object(campaign,'validate',return_value=prepared), \
             patch.object(campaign,'verify_availability'),patch.object(campaign,'validate_age'), \
             patch.object(campaign,'operator_authenticate'),patch.object(campaign,'Gateway',return_value=self.gateway):
            campaign.main()

    def test_exactly_24_posts_and_resume_never_reposts(self):
        self.run_campaign()
        self.assertEqual(len(self.posts),24)
        self.run_campaign()
        self.assertEqual(len(self.posts),24)

    def test_prompt_mutation_blocks_before_auth_or_post(self):
        self.plan[0]['prompt'] += ' modified'
        (self.private/'execution-plan-v1.private.json').write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError,'matrix mismatch'):
            self.run_campaign()
        self.assertEqual(self.posts,[])

    def test_insufficient_full_batch_quota_blocks_all_posts(self):
        with patch.object(campaign,'quota_balance',return_value=43):
            with self.assertRaisesRegex(ValueError,'Insufficient quota'):
                self.run_campaign()
        self.assertEqual(self.posts,[])

    def test_ambiguous_post_is_not_retried_on_resume(self):
        original=self.gateway.request
        def lost_response(method,path,payload=None):
            result=original(method,path,payload)
            if method == 'POST':
                raise TimeoutError('Simulated lost submission response')
            return result
        with patch.object(self.gateway,'request',side_effect=lost_response):
            with self.assertRaises(TimeoutError):
                self.run_campaign()
        self.assertEqual(len(self.posts),1)
        with self.assertRaisesRegex(ValueError,'Ambiguous claim'):
            self.run_campaign()
        self.assertEqual(len(self.posts),1)


if __name__ == '__main__':
    unittest.main()
