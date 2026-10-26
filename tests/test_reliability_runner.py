"""Critical quota, crash-recovery and reconciliation invariants; no network."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import hashlib

spec = importlib.util.spec_from_file_location('reliability_runner', Path(__file__).resolve().parents[1] / 'scripts/reliability_runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runner = module.Runner(self.temp.name, cap=1)
        self.entry = dict(experiment_id='A-001', stage='A')
        self.payload = dict(Prompt='Observe visible action', VideoUris=['private-reference'])

    def tearDown(self):
        self.runner.db.close()
        self.temp.cleanup()

    def test_ambiguous_claim_survives_restart_and_blocks_new_request(self):
        self.runner.reserve(self.entry, self.payload, 500)
        self.runner.db.close()
        self.runner = module.Runner(self.temp.name)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.runner.reserve(dict(experiment_id='A-002',stage='A'),self.payload,500)

    def test_headroom_and_local_cap(self):
        with self.assertRaises(ValueError):
            self.runner.reserve(self.entry,self.payload,20)
        self.runner.reserve(self.entry,self.payload,500)
        self.runner.db.execute("UPDATE requests SET state='valid_model_decision',summary_id='abc'")
        self.runner.db.commit()
        with self.assertRaisesRegex(ValueError, 'cap'):
            self.runner.reserve(dict(experiment_id='A-002',stage='A'),self.payload,499)

    def test_reconciliation_requires_exact_payload(self):
        self.runner.reserve(self.entry,self.payload,500)
        class WrongGateway:
            def request(self,*args):
                return dict(Id='abc',Prompt='Different prompt',VideoUris=['private-reference'])
        with self.assertRaisesRegex(ValueError,'exact'):
            self.runner.reconcile(WrongGateway(),'A-001','abc')
        class CorrectGateway:
            def request(inner,*args):
                return dict(Id='abc',**self.payload)
        self.runner.reconcile(CorrectGateway(),'A-001','abc')
        self.assertEqual(self.runner.db.execute('SELECT summary_id FROM requests').fetchone()[0],'abc')

    def test_human_review_gate(self):
        with self.assertRaisesRegex(ValueError,'human review'):
            list(module.validate([],dict(status='AI_draft')))

    def test_authorized_demo_review_is_distinct_from_human_attestation(self):
        artifact = Path(self.temp.name) / 'review.json'
        artifact.write_text('{"review_mode":"ai_demo"}')
        review = dict(status='reviewed', review_mode='ai_demo', user_authorized_ai_review=True,
            reviewer='AI',reviewed_at='2026-10-26T18:00:00Z',review_artifact=str(artifact),
            review_artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
            definitions_sha256=hashlib.sha256((module.REPO / 'docs/reliability/label-definitions.json').read_bytes()).hexdigest())
        self.assertEqual(list(module.validate([],review)),[])
        review['user_authorized_ai_review'] = False
        with self.assertRaisesRegex(ValueError,'explicitly authorized'):
            list(module.validate([],review))

    def test_cap_cannot_exceed_headroom(self):
        with self.assertRaises(ValueError):
            module.Runner(self.temp.name,481)

    def test_pending_resume_blocks_new_submissions_even_after_restart(self):
        self.runner.reserve(self.entry,self.payload,500)
        self.runner.db.execute("UPDATE requests SET state='pending',summary_id='abc'")
        self.runner.db.commit()
        self.runner.db.close()
        self.runner = module.Runner(self.temp.name)
        with self.assertRaisesRegex(ValueError, 'in flight'):
            self.runner.reserve(dict(experiment_id='A-002',stage='A'),self.payload,499)

    def test_resume_waits_for_completion(self):
        self.runner.reserve(self.entry,self.payload,500)
        self.runner.db.execute("UPDATE requests SET state='submitted',summary_id='abc'")
        self.runner.db.commit()
        class PendingGateway:
            def request(self,*args):
                return dict(Id='abc',Progress='Processing')
        with self.assertRaises(TimeoutError):
            module.await_summary(self.runner,PendingGateway(),'A-001','abc',timeout=0)
        self.assertEqual(self.runner.db.execute('SELECT state FROM requests').fetchone()[0],'pending')

    def test_poll_cannot_replace_another_experiments_response(self):
        self.runner.reserve(self.entry,self.payload,500)
        self.runner.db.execute("UPDATE requests SET state='submitted',summary_id='abc'")
        self.runner.db.commit()
        class WrongGateway:
            def request(self,*args):
                return dict(Id='def',Progress='Completed',Response='private')
        with self.assertRaisesRegex(ValueError,'identity'):
            self.runner.poll(WrongGateway(),'A-001','abc')
        with self.assertRaisesRegex(ValueError,'bound'):
            self.runner.poll(WrongGateway(),'A-001','def')
        self.assertEqual(self.runner.db.execute('SELECT result FROM requests').fetchone()[0],None)

    def test_invalid_quota_is_rejected_before_reservation(self):
        for remaining in (True,501,-1,'500'):
            with self.assertRaises(ValueError):
                self.runner.reserve(self.entry,self.payload,remaining)
        self.assertEqual(self.runner.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
