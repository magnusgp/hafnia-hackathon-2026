"""Critical quota, crash-recovery and reconciliation invariants; no network."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

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
        self.runner.db.execute("UPDATE requests SET state='submitted',summary_id='abc'")
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

    def test_cap_cannot_exceed_headroom(self):
        with self.assertRaises(ValueError):
            module.Runner(self.temp.name,481)
