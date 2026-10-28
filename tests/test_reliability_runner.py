"""Critical quota, crash-recovery and reconciliation invariants; no network."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import hashlib
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reliability_runner', Path(__file__).resolve().parents[1] / 'scripts/reliability_runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RunnerTests(unittest.TestCase):
    def test_diagnostic_prose_preserved_without_incident_json_requirement(self):
        text = 'A person walks to the platform edge, then sits down.'
        parsed = module.parse_descriptive(dict(Progress='Completed',Response=text))
        self.assertEqual(parsed['category'],'valid_descriptive_response')
        self.assertEqual(parsed['literal_response'],text)
        self.assertIsNone(parsed['outcome'])
        self.assertEqual(parsed['semantic_review'],'pending')
        for state,category in [('Processing','pending'),('Failed','gateway_inference_failure')]:
            self.assertEqual(module.parse_descriptive(dict(Progress=state))['category'],category)
        self.assertEqual(module.parse_descriptive(dict(Progress='Completed',Response=' '))['category'],'empty_response')

    def test_descriptive_completion_allows_next_claim_and_preserves_raw(self):
        self.runner.descriptive = True
        self.runner.reserve(self.entry,self.payload,500)
        class Gateway:
            def request(inner,*args):
                return dict(Id='abc',Progress='Completed',Response='Visible person near a gate.',
                            Request=dict(**self.payload,AiModelId='traffic-general'))
        self.runner.reconcile(Gateway(),'A-001','abc')
        self.assertEqual(self.runner.poll(Gateway(),'A-001','abc'),'valid_descriptive_response')
        stored=json.loads(self.runner.db.execute('SELECT result FROM requests').fetchone()[0])
        self.assertEqual(stored['raw']['Request']['AiModelId'],'traffic-general')
        self.runner.cap=480
        self.runner.reserve(dict(experiment_id='A-002',stage='A'),self.payload,499)

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
                return dict(Id='abc',Request=dict(**self.payload,AiModelId='traffic-general'))
        self.runner.reconcile(CorrectGateway(),'A-001','abc')
        self.assertEqual(self.runner.db.execute('SELECT summary_id FROM requests').fetchone()[0],'abc')

    def test_reconciliation_rejects_top_level_echo_with_wrong_returned_request(self):
        self.runner.reserve(self.entry,self.payload,500)
        class Gateway:
            def request(inner,*args):
                return dict(Id='abc',Request=dict(Prompt='wrong',VideoUris=['private-reference']),**self.payload)
        with self.assertRaisesRegex(ValueError,'exact'):
            self.runner.reconcile(Gateway(),'A-001','abc')
        self.assertIsNone(self.runner.db.execute('SELECT summary_id FROM requests').fetchone()[0])

    def test_human_review_gate(self):
        with self.assertRaisesRegex(ValueError,'human review'):
            list(module.validate([],dict(status='AI_draft')))

    def test_authorized_demo_review_is_distinct_from_human_attestation(self):
        artifact = Path(self.temp.name) / 'review.json'
        artifact.write_text('{"review_mode":"ai_demo"}')
        review = dict(status='reviewed', review_mode='ai_demo', user_authorized_ai_review=True,
            reviewer='AI',reviewed_at='2026-10-26T18:00:00Z',review_artifact=str(artifact),
            review_artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
            definitions_sha256=hashlib.sha256((module.REPO / 'docs/research/reliability/label-definitions.json').read_bytes()).hexdigest())
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

    def test_unverified_or_stale_recording_blocks_before_inference(self):
        entry = dict(event_id='railway-loop-001',manifest_sha256='source',
                     start='2026-10-22T11:03:39Z',end='2026-10-22T11:03:52Z')
        now = datetime(2026,10,26,22,tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError,'unverified'):
            module.verify_availability(entry,{},now)
        proof = Path(self.temp.name)/'coverage.json'
        proof.write_text('{"recording_coverage":"synthetic test fixture"}')
        check = dict(event_id=entry['event_id'],manifest_sha256='source',available=True,
            checked_by='Test operator',checked_at=now.isoformat(),coverage_start=entry['start'],
            coverage_end=entry['end'],evidence_file=str(proof),
            evidence_sha256=hashlib.sha256(proof.read_bytes()).hexdigest())
        module.verify_availability(entry,dict(recordings=[check]),now)
        with self.assertRaisesRegex(ValueError,'15 minutes'):
            module.verify_availability(entry,dict(recordings=[check]),now+timedelta(minutes=16))
        check['coverage_end'] = '2026-10-22T11:03:51Z'
        with self.assertRaisesRegex(ValueError,'coverage'):
            module.verify_availability(entry,dict(recordings=[check]),now)

    def test_operator_login_ignores_stale_environment(self):
        class FakeGateway:
            def request(inner,method,path,payload,login):
                self.assertEqual(payload['Password'],'typed-in-terminal')
                self.assertTrue(login)
                return dict(Id='private-test-session')
        gateway = FakeGateway()
        with patch.dict('os.environ',{'HAFNIA_GW_PASSWORD':'stale-value'}), \
             patch.object(module.sys.stdin,'isatty',return_value=True), \
             patch.object(module.getpass,'getpass',return_value='typed-in-terminal'):
            module.operator_authenticate(gateway)
        self.assertEqual(gateway.session,'private-test-session')

    def test_original_manifest_without_frame_hash_uses_frozen_review_hash(self):
        root = Path(self.temp.name)
        frame = root/'frame.jpg'; frame.write_bytes(b'private structural fixture')
        manifest = root/'manifest.json'
        camera = '11111111-1111-1111-1111-111111111111'
        start = (datetime.now(timezone.utc)-timedelta(hours=1)).replace(microsecond=0)
        end = start+timedelta(seconds=13)
        timestamp = (start+timedelta(seconds=1)).isoformat()
        manifest.write_text(json.dumps(dict(camera_id=camera,requested_start_utc=start.isoformat(),
            requested_end_utc=end.isoformat(),frames=[dict(file='frame.jpg',timestamp_utc=timestamp)])))
        artifact = root/'review.json'
        artifact.write_text(json.dumps(dict(sources=[dict(event_id='gate-loop-001',
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            frames=[dict(timestamp_utc=timestamp,sha256=hashlib.sha256(frame.read_bytes()).hexdigest())])])) )
        review = dict(status='reviewed',review_mode='ai_demo',user_authorized_ai_review=True,
            reviewer='AI',reviewed_at='2026-10-26T22:00:00Z',review_artifact=str(artifact),
            review_artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
            definitions_sha256=hashlib.sha256((module.REPO/'docs/research/reliability/label-definitions.json').read_bytes()).hexdigest())
        entry = dict(experiment_id='REL26-B-gate-v3-r01',stage='B',event_id='gate-loop-001',
            prompt='Visible gate manipulation',camera_id=camera,start=start.isoformat(),
            end=end.isoformat(),recording_manifest=str(manifest),
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            label_review_sha256=review['review_artifact_sha256'],continuity_review='ai_reviewed_no_loop_boundary')
        self.assertEqual(len(list(module.validate([entry],review))),1)
        frame.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            list(module.validate([entry],review))

    def test_recording_age_boundary_and_future_are_rejected(self):
        now=datetime(2026,10,26,22,tzinfo=timezone.utc)
        for start,end in [(now-timedelta(hours=24),now-timedelta(hours=24)+timedelta(seconds=13)),
                          (now-timedelta(days=4),now-timedelta(days=4)+timedelta(seconds=13)),
                          (now,now+timedelta(seconds=13))]:
            with self.assertRaisesRegex(ValueError,'24 hours'):
                module.validate_age(dict(start=start.isoformat(),end=end.isoformat()),now)
        module.validate_age(dict(start=(now-timedelta(hours=1)).isoformat(),
                                 end=(now-timedelta(hours=1)+timedelta(seconds=13)).isoformat()),now)

    def test_authenticated_preflight_never_submits_a_summary(self):
        root=Path(self.temp.name)
        plan=root/'input-plan.json';plan.write_text('[]')
        artifact=root/'review-artifact.json';artifact.write_text('{"sources":[]}')
        review=root/'review.json';review.write_text(json.dumps(dict(status='reviewed',review_mode='ai_demo',
            user_authorized_ai_review=True,reviewer='AI',reviewed_at='2026-10-26T22:00:00Z',
            review_artifact=str(artifact),review_artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
            definitions_sha256=hashlib.sha256((module.REPO/'docs/research/reliability/label-definitions.json').read_bytes()).hexdigest())))
        calls=[]
        class ReadOnlyGateway:
            def request(self,method,path):
                calls.append((method,path))
                return []
        args=['runner','--root',str(root/'preflight'),'--plan',str(plan),'--review',str(review),
              '--authenticated-preflight','--operator-auth-confirmed']
        with patch.object(module.sys,'argv',args),patch.object(module,'Gateway',ReadOnlyGateway), \
             patch.object(module,'operator_authenticate') as login:
            module.main()
        login.assert_called_once()
        self.assertEqual(calls,[('GET','/api/Summaries?Limit=1'),('GET','/api/System/Information')])
        proof=json.loads((root/'preflight/authenticated-preflight.json').read_text())
        self.assertTrue(proof['success'])
        self.assertEqual(proof['new_summaries'],0)
        with module.sqlite3.connect(root/'preflight/reliability-ledger.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        db.close()

    def test_preflight_and_apply_cannot_be_combined(self):
        with patch.object(module.sys,'argv',['runner','--root',self.temp.name,'--apply','--authenticated-preflight']), \
             patch.object(module,'Gateway') as gateway:
            with self.assertRaises(SystemExit):module.main()
        gateway.assert_not_called()

    def test_installed_quota_schema_enforces_cap_count_and_reset(self):
        now=datetime(2026,10,26,22,tzinfo=timezone.utc)
        contract=dict(kind='gateway_system_information',endpoint='/api/System/Information')
        q=dict(DailySummaryQuota=500,DailySummaryCount=16,DailySummaryReset='2026-10-27T00:00:00Z')
        self.assertEqual(module.quota_balance(dict(QuotaInformation=q),contract,now),484)
        for key,value in [('DailySummaryCount',True),('DailySummaryQuota',1000),
                          ('DailySummaryReset','2026-10-26T00:00:00Z')]:
            bad=dict(q);bad[key]=value
            with self.assertRaises(ValueError):module.quota_balance(dict(QuotaInformation=bad),contract,now)
