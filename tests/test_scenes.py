import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import scene26
from scene_contracts.contracts import assess, load_contracts
from scene_contracts.store import Store, interval
from scene_contracts.xprotect import XProtect, XProtectError, NoRedirect, associate

FIXTURES = Path(__file__).parent / 'fixtures'
CAMERA = '00000000-0000-0000-0000-000000000001'
ALARM = '00000000-0000-0000-0000-000000000002'
START, END = '2026-10-19T12:00:00Z', '2026-10-19T12:00:15Z'


def fixture(kind='positive'):
    return json.loads((FIXTURES / f'completed-{kind}.json').read_text())


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contracts()[0]

    def test_outcomes(self):
        for kind in ('positive', 'negative', 'uncertain'):
            self.assertEqual(assess(self.contract, fixture(kind))['outcome'], kind)

    def test_malformed_never_positive(self):
        good = fixture()['Response']
        bad = [None, {}, '', good + '\nDECISION: H26_DAMAGE_EVENT', good + '\nprose',
               good.replace('DECISION:', 'decision:'), good.replace('H26_DAMAGE_EVENT', 'UNKNOWN'),
               good.replace('LIMITATIONS:', 'OTHER:'), good + '\nLIMITATIONS: extra',
               good.replace('Intent and identity cannot be established.', 'H26_NO_DAMAGE_EVENT'),
               good.replace('VISIBLE_CHANGE: The intact pane fractures immediately after the strike.', 'VISIBLE_CHANGE:')]
        for response in bad:
            with self.subTest(response=response):
                self.assertEqual(assess(self.contract, {**fixture(), 'Response': response})['outcome'], 'uncertain')
        for status in ('Failed', 'Running', None):
            self.assertEqual(assess(self.contract, {**fixture(), 'Progress': status})['outcome'], 'uncertain')

    def test_missing_evidence(self):
        for evidence in ('none established', 'unknown', '<before/after>', 'No visible change in this clip', 'not visible', 'N/A'):
            item = fixture()
            item['Response'] = item['Response'].replace('The intact pane fractures immediately after the strike.', evidence)
            self.assertEqual(assess(self.contract, item)['outcome'], 'uncertain')

    def test_generic_contract(self):
        c = copy.deepcopy(self.contract)
        c.update(outcomes={'BLOCKED': 'positive', 'CLEAR': 'negative', 'UNKNOWN': 'uncertain'},
                 response_fields=['EVIDENCE'], positive_evidence_fields=['EVIDENCE'])
        result = assess(c, {'Progress': 'Completed', 'Response': 'DECISION: BLOCKED\nEVIDENCE: A box visibly obstructs the doorway.'})
        self.assertEqual(result['outcome'], 'positive')

    def test_invalid_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'c.json'
            for key in ('outcomes', 'positive_evidence_fields', 'camera_names', 'assessment_prompt'):
                c = copy.deepcopy(self.contract)
                c[key] = None
                p.write_text(json.dumps(c))
                with self.assertRaises(ValueError):
                    load_contracts(tmp)

    def test_interval(self):
        self.assertEqual(interval('2026-10-19T14:00:00+02:00', END), (START, END))
        for a, b in ((END, START), (START, START), ('2026-10-19T12:00:00', END)):
            with self.assertRaises(ValueError):
                interval(a, b)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'cases.sqlite3'
        self.store = Store(self.path)
        self.contract = load_contracts()[0]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ingest(self, kind='positive', **changes):
        return self.store.ingest(self.contract, {**fixture(kind), **changes}, CAMERA, 'vandalism', START, END)

    def test_idempotency_conflicts_and_reopen(self):
        first, created = self.ingest()
        self.assertTrue(created)
        self.assertFalse(self.ingest()[1])
        with self.assertRaises(ValueError):
            self.ingest(Response='different')
        self.assertEqual(len(self.store.case(first['case_id'])['observations']), 1)
        self.store.close()
        self.store = Store(self.path)
        self.assertFalse(self.ingest()[1])
        self.assertIn('fractures', self.store.case(first['case_id'])['observations'][0]['raw_response']['Response'])

    def test_cases_are_not_independent_incidents(self):
        a, _ = self.ingest()
        b, _ = self.ingest(Id='loop-again')
        self.assertEqual(a['case_id'], b['case_id'])
        self.assertEqual(len(self.store.cases()), 1)
        self.assertEqual(len(self.store.case(a['case_id'])['observations']), 2)

    def test_transitions(self):
        row, _ = self.ingest('negative')
        cid = row['case_id']
        self.assertEqual(self.store.case(cid)['state'], 'observed')
        self.ingest('uncertain')
        self.assertEqual(self.store.case(cid)['state'], 'review_required')
        self.store.review(cid, 'Operator inspected footage; local review only')
        self.assertEqual(self.store.case(cid)['state'], 'reviewed')
        self.ingest('negative', Id='later-negative')
        self.assertEqual(self.store.case(cid)['state'], 'reviewed')
        self.ingest()
        self.assertEqual(self.store.case(cid)['state'], 'review_required')
        self.ingest('negative', Id='another-negative')
        self.assertEqual(self.store.case(cid)['state'], 'review_required')
        self.assertTrue(self.store.case(cid)['history'])
        with self.assertRaises(ValueError):
            self.store.review(cid, ' ')

    def test_failed_and_invalid(self):
        row, _ = self.ingest(Progress='Failed')
        self.assertEqual(row['outcome'], 'uncertain')
        for change in ({'Id': ''}, {'Id': 'pending', 'Progress': 'Running'}):
            with self.assertRaises(ValueError):
                self.ingest(**change)
        self.assertEqual(len(self.store.cases()), 1)

    def test_contract_provenance_conflict(self):
        self.ingest()
        self.contract['version'] = '2'
        with self.assertRaises(ValueError):
            self.ingest()

    def test_association_requires_operator_and_unique_candidate(self):
        row, _ = self.ingest()
        cid = row['case_id']
        client = Mock()
        alarm = {'id': ALARM, 'source': f'cameras/{CAMERA}', 'name': 'Demo', 'time': '2026-10-19T12:00:05.1234567Z'}
        client.collection.return_value = [alarm]
        self.assertEqual(associate(self.store, client, cid, START, END, 'Demo')['status'], 'unconfirmed')
        linked = associate(self.store, client, cid, START, END, 'Demo', ALARM, 'Verified in Smart Client')
        self.assertEqual(linked['alarm_id'], ALARM)
        client.collection.return_value = [alarm, {**alarm, 'id': CAMERA}]
        self.assertEqual(associate(self.store, client, cid, START, END, 'Demo')['status'], 'ambiguous')
        with self.assertRaises(ValueError):
            associate(self.store, client, cid, START, END, 'Demo', ALARM, 'pick one')
        checks = self.store.case(cid)['alarm_checks']
        self.assertEqual(checks[-1]['status'], 'ambiguous')
        self.assertIsNone(checks[-1]['alarm_id'])
        client.collection.return_value = []
        self.assertEqual(associate(self.store, client, cid, START, END, 'Demo')['status'], 'not_found')
        self.assertTrue(all(call[0] == 'collection' for call in client.method_calls))


class CLITests(unittest.TestCase):
    def test_dry_run_no_network_or_db(self):
        args = scene26.parser().parse_args(['evaluate', '--contract', 'property-damage', '--camera', 'vandalism',
            '--camera-id', CAMERA, '--start', START, '--end', END])
        with patch('scene26.Gateway') as gateway, patch('scene26.Store') as store, redirect_stdout(io.StringIO()):
            scene26.run(args)
            gateway.assert_not_called()
            store.assert_not_called()

    def test_camera_map_exact_and_unique(self):
        c = load_contracts()[0]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'c.json'
            args = Mock(camera='vandalism', camera_map=str(p), camera_id=None)
            p.write_text(json.dumps([{'Name': 'vandalism', 'Id': CAMERA}]), encoding='utf-8-sig')
            self.assertEqual(scene26.camera(args, c), CAMERA)
            p.write_text(json.dumps([{'Name': 'vandalism', 'Id': CAMERA}] * 2))
            with self.assertRaises(ValueError):
                scene26.camera(args, c)

    def test_ingest_no_vlm(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = scene26.parser().parse_args(['--db', str(Path(tmp) / 'db'), 'ingest', '--contract', 'property-damage',
                '--camera', 'vandalism', '--camera-id', CAMERA, '--start', START, '--end', END,
                '--file', str(FIXTURES / 'completed-positive.json')])
            with patch('scene26.Gateway') as gateway, redirect_stdout(io.StringIO()):
                scene26.run(args)
                scene26.run(args)
                gateway.assert_not_called()
            store = Store(args.db)
            self.assertEqual(len(store.case(1)['observations']), 1)
            store.close()


class XProtectTests(unittest.TestCase):
    def test_https_and_redirect(self):
        for url in ('http://localhost', 'https://user:secret@localhost', 'https://localhost/path'):
            with self.assertRaises(ValueError):
                XProtect(url)
        with self.assertRaises(XProtectError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere')

    def test_auth_form_and_no_token_output(self):
        client = XProtect('https://localhost')
        with patch.dict('os.environ', {'XPROTECT_USERNAME': 'test', 'XPROTECT_PASSWORD': 'private'}, clear=True), patch.object(client, '_request', return_value={'access_token': 'private-token'}) as request:
            client.authenticate()
        self.assertEqual(request.call_args.args[0], '/API/IDP/connect/token')
        self.assertEqual(request.call_args.args[1]['grant_type'], 'password')
        self.assertEqual(client.token, 'private-token')

    def test_pagination_and_failure_closed(self):
        client = XProtect('https://localhost')
        with patch.object(client, '_request', side_effect=[{'array': [{'id': str(i)} for i in range(200)]}, {'array': [{'id': 'last'}]}]) as request:
            self.assertEqual(len(client.collection('alarms', START, END, CAMERA)), 201)
            self.assertEqual(parse_qs(urlsplit(request.call_args.args[0]).query)['page'], ['1'])
        with patch.object(client, '_request', return_value={'data': []}):
            with self.assertRaises(XProtectError):
                client.collection('alarms', START, END)
        with patch.object(client.opener, 'open', side_effect=HTTPError('https://localhost', 401, 'private-token', {}, None)):
            with self.assertRaises(XProtectError) as caught:
                client._request('/api/rest/v1/alarms')
            self.assertNotIn('private-token', str(caught.exception))


class EvaluationTests(unittest.TestCase):
    def test_applied_evaluation_saves_manifest_and_submits_once(self):
        contract = load_contracts()[0]
        with tempfile.TemporaryDirectory() as tmp:
            args = Mock(camera='vandalism', apply=True, output_dir=tmp, max_wait=10)
            client = Mock()
            client.exact_item.return_value = {'Id': 'prompt-id', 'Text': contract['assessment_prompt']}
            initial = {'Id': 'fixture-positive-001', 'Progress': 'Running'}
            client.request.side_effect = [initial, fixture()]
            with patch('scene26.Gateway', return_value=client), patch('scene26.time.sleep'), redirect_stdout(io.StringIO()):
                item = scene26.evaluate(args, contract, CAMERA, START, END)
            self.assertEqual(item['Progress'], 'Completed')
            self.assertEqual([c.args[0] for c in client.request.call_args_list], ['POST', 'GET'])
            payload = client.request.call_args_list[0].args[2]
            self.assertNotIn('PromptId', payload)
            client.exact_item.assert_not_called()
            self.assertEqual(payload['Prompt'], contract['assessment_prompt'])
            manifest = json.loads(next(Path(tmp).glob('*.json')).read_text())
            self.assertEqual(manifest['result'], fixture())
            self.assertEqual(manifest['contract'], contract)
            self.assertEqual(manifest['camera_id'], CAMERA)

    def test_poll_failure_preserves_submitted_identity(self):
        from scene_contracts.gateway import GatewayError
        contract = load_contracts()[0]
        with tempfile.TemporaryDirectory() as tmp:
            args = Mock(camera='vandalism', apply=True, output_dir=tmp, max_wait=10)
            client = Mock()
            client.exact_item.return_value = {'Id': 'prompt-id', 'Text': contract['assessment_prompt']}
            initial = {'Id': 'recover-this-id', 'Progress': 'Running'}
            client.request.side_effect = [initial, GatewayError('Offline')]
            with patch('scene26.Gateway', return_value=client), patch('scene26.time.sleep'), redirect_stdout(io.StringIO()):
                with self.assertRaises(GatewayError):
                    scene26.evaluate(args, contract, CAMERA, START, END)
            manifest = json.loads(next(Path(tmp).glob('*.json')).read_text())
            self.assertEqual(manifest['result']['Id'], 'recover-this-id')
            self.assertEqual(len(client.request.call_args_list), 2)

    def test_saved_prompt_is_never_resolved_by_scene_contracts(self):
        contract = load_contracts()[0]
        with tempfile.TemporaryDirectory() as tmp:
            args = Mock(camera='vandalism', apply=True, output_dir=tmp, max_wait=10)
            client = Mock()
            client.exact_item.return_value = {'Id': 'prompt-id', 'Text': 'different'}
            client.request.return_value = fixture()
            with patch('scene26.Gateway', return_value=client), redirect_stdout(io.StringIO()):
                scene26.evaluate(args, contract, CAMERA, START, END)
            client.exact_item.assert_not_called()
            self.assertNotIn('PromptId', client.request.call_args.args[2])

    def test_existing_summary_uses_only_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = scene26.parser().parse_args(['--db', str(Path(tmp) / 'db'), 'ingest', '--contract', 'property-damage',
                '--camera', 'vandalism', '--camera-id', CAMERA, '--start', START, '--end', END,
                '--summary-id', 'fixture-positive-001'])
            client = Mock()
            client.request.return_value = fixture()
            with patch('scene26.Gateway', return_value=client), redirect_stdout(io.StringIO()):
                scene26.run(args)
            client.request.assert_called_once_with('GET', '/api/Summaries/fixture-positive-001')


class GatewaySecurityTests(unittest.TestCase):
    def test_local_https_and_redirects(self):
        from scene_contracts.gateway import Gateway, GatewayError, NoRedirect
        for url in ('http://localhost', 'https://example.com', 'https://user:secret@localhost'):
            with self.assertRaises(GatewayError):
                Gateway(url)
        with self.assertRaises(GatewayError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere')
        client = Gateway()
        with patch.object(client.opener, 'open', side_effect=HTTPError('https://localhost', 401, 'private-password', {}, None)):
            with self.assertRaises(GatewayError) as caught:
                client.request('POST', '/api/Sessions/Login', {'Password': 'private-password'}, login=True)
            self.assertNotIn('private-password', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
