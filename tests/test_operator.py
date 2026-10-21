"""Synthetic protocol tests only. Never contact Hafnia or XProtect."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.request import build_opener, HTTPRedirectHandler, Request
from urllib.error import HTTPError
from urllib.parse import urlencode

import hack26
import scene_web
from scene_contracts.contracts import DEFAULT_CONTRACTS
from scene_contracts.gateway import GatewayError
from scene_contracts.operator import Operator
from scene_contracts.store import Store

CAMERA = '00000000-0000-0000-0000-000000000001'
START, END = '2026-10-19T12:00:00Z', '2026-10-19T12:00:15Z'


def result(decision='SC_BREACH', sid='synthetic-summary'):
    return {'Id': sid, 'Progress': 'Completed', 'Response': f'DECISION: {decision}\nOBSERVATIONS: Fog obscures distant vehicles.\nVISIBLE_EVIDENCE: Lane boundaries disappear behind dense fog.\nLIMITATIONS: Distances cannot be measured.'}


class OperatorFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.map = self.path / 'cameras.local.json'
        self.map.write_text(json.dumps([{'Name': name, 'Id': CAMERA} for name in ['vandalism', 'highway_traffic_overcast_weather']]))
        self.store = Store(self.path / 'cases.sqlite3')
        self.addCleanup(lambda: self.store.close())
        self.op = Operator(self.store, str(self.map), DEFAULT_CONTRACTS)

    def preview(self):
        return self.op.preview('roadway-visibility', 'highway_traffic_overcast_weather', START, END)


class OperatorTests(OperatorFixture):
    def test_preview_exact_payload_offline(self):
        with patch('scene_contracts.operator.Gateway') as gateway:
            job = self.op.request(self.preview())
        gateway.assert_not_called()
        self.assertEqual(job['status'], 'preview')
        self.assertEqual(set(job['metadata']['payload']), {'Prompt', 'VideoUris'})
        self.assertIn('StartTime=' + START, job['metadata']['payload']['VideoUris'][0])
        self.assertEqual(job['metadata']['payload']['Prompt'], job['metadata']['contract']['assessment_prompt'])
        self.assertEqual(self.store.cases(), [])

    def test_live_client_requires_process_credential_without_prompting(self):
        with patch.dict('os.environ', {}, clear=True), patch('scene_contracts.operator.Gateway') as gateway:
            with self.assertRaises(GatewayError):
                self.op.client()
        gateway.assert_not_called()

    def test_native_alarm_checks_are_displayed_without_implied_link(self):
        request_id = self.preview()
        self.op.import_result(request_id, result())
        self.store.record_alarm_check(1, 'ambiguous', None, {'candidates': [{'id': 'candidate-one'}, {'id': 'candidate-two'}]})
        html = scene_web.Console(self.op, 'token').case(1)
        self.assertIn('ambiguous', html)
        self.assertIn('No confirmed association', html)
        self.assertIn('candidate-two', html)
        self.assertNotIn('operator_confirmed', html)

    def test_camera_and_interval_validation(self):
        for camera, start, end in [('unknown', START, END), ('vandalism', START, END), ('highway_traffic_overcast_weather', END, START), ('highway_traffic_overcast_weather', '2026-10-19T12:00:00', END)]:
            with self.assertRaises(ValueError):
                self.op.preview('roadway-visibility', camera, start, end)
        self.map.write_text(json.dumps([{'Name': 'highway_traffic_overcast_weather', 'Id': CAMERA}] * 2))
        with self.assertRaises(ValueError):
            self.preview()

    def test_fixed_contract_and_persistence(self):
        c = self.op.create_contract('Road watch', 'highway_traffic_overcast_weather', 'All visible lanes remain distinguishable.')
        self.assertNotIn('gateway_prompt_title', c)
        self.assertIn(json.dumps(c['expected_condition']), c['assessment_prompt'])
        self.store.close()
        self.store = Store(self.path / 'cases.sqlite3')
        self.op = Operator(self.store, str(self.map), DEFAULT_CONTRACTS)
        self.assertEqual(self.op.contracts()[-1], c)
        for name, camera, condition in [('', 'vandalism', 'Visible.'), ('Name', 'missing', 'Visible.'), ('Name', 'vandalism', '\nRules'), ('Name', 'vandalism', 'x' * 1001)]:
            with self.assertRaises(ValueError):
                self.op.create_contract(name, camera, condition)

    def test_submission_is_claimed_once_and_poll_is_get_only(self):
        request_id = self.preview()
        client = Mock()
        client.request.side_effect = [{'Id': 'synthetic-summary', 'Progress': 'Running'}, result()]
        with patch.object(self.op, 'client', return_value=client):
            self.op.submit(request_id)
            self.op.submit(request_id)
            self.assertEqual(self.op.request(request_id)['status'], 'running')
            self.op.refresh(request_id)
            self.op.refresh(request_id)
        self.assertEqual([c.args[0] for c in client.request.call_args_list], ['POST', 'GET'])
        self.assertNotIn('PromptId', client.request.call_args_list[0].args[2])
        self.assertEqual(self.op.request(request_id)['status'], 'completed')
        self.assertEqual(len(self.store.case(1)['observations']), 1)

    def test_submission_failure_and_restart_never_retry(self):
        request_id = self.preview()
        client = Mock()
        client.request.side_effect = GatewayError('secret-token')
        with patch.object(self.op, 'client', return_value=client):
            self.op.submit(request_id)
            self.op.submit(request_id)
        self.assertEqual(client.request.call_count, 1)
        self.assertEqual(self.op.request(request_id)['status'], 'attention')
        self.assertNotIn('secret-token', self.op.request(request_id)['message'])
        self.store.close()
        self.store = Store(self.path / 'cases.sqlite3')
        self.op = Operator(self.store, str(self.map), DEFAULT_CONTRACTS)
        with patch.object(self.op, 'client') as connect:
            self.op.submit(request_id)
        connect.assert_not_called()
        self.op.import_result(request_id, result())
        self.assertEqual(self.op.request(request_id)['status'], 'completed')

    def test_pending_survives_fetch_failure_and_recovers(self):
        request_id = self.preview()
        self.op.update(request_id, 'running', 'synthetic-summary')
        client = Mock()
        client.request.side_effect = [GatewayError('sensitive-response'), result()]
        with patch.object(self.op, 'client', return_value=client):
            self.op.refresh(request_id)
            self.assertEqual(self.op.request(request_id)['summary_id'], 'synthetic-summary')
            self.op.refresh(request_id)
        self.assertTrue(all(c.args[0] == 'GET' for c in client.request.call_args_list))
        self.assertEqual(self.op.request(request_id)['status'], 'completed')

    def test_claim_is_atomic_across_connections(self):
        request_id = self.preview()
        other = Store(self.path / 'cases.sqlite3')
        self.addCleanup(other.close)
        op2 = Operator(other, str(self.map), DEFAULT_CONTRACTS)
        self.assertTrue(self.op.claim(request_id, 'submitting'))
        self.assertFalse(op2.claim(request_id, 'submitting'))
        with patch.object(op2, 'client') as client:
            op2.submit(request_id)
        client.assert_not_called()
        with self.assertRaises(ValueError):
            op2.import_result(request_id, result())

    def test_import_and_reviews_survive_restart_without_gateway(self):
        request_id = self.preview()
        with patch('scene_contracts.operator.Gateway') as gateway:
            self.op.import_result(request_id, result())
        gateway.assert_not_called()
        self.store.review(1, 'Verified the recording; visibility is restricted.')
        self.store.close()
        self.store = Store(self.path / 'cases.sqlite3')
        c = self.store.case(1)
        self.assertEqual(c['state'], 'reviewed')
        self.assertEqual(c['history'][-1]['kind'], 'operator_review')
        self.assertEqual(c['observations'][0]['summary_id'], 'synthetic-summary')
        self.assertEqual(c['observations'][0]['raw_response'], result())

    def test_import_rejects_provenance_identity_and_pending(self):
        request_id = self.preview()
        for item in [{**result(), 'VideoUris': ['different-recording']}, {**result(), 'Progress': 'Running'}, {'result': result()}]:
            with self.assertRaises(ValueError):
                self.op.import_result(request_id, item)
        self.assertEqual(self.op.request(request_id)['status'], 'preview')
        self.op.update(request_id, 'running', 'original-id')
        with self.assertRaises(ValueError):
            self.op.import_result(request_id, result())
        self.assertEqual(self.store.cases(), [])

    def test_malformed_uncertain_negative_have_no_positive_event_path(self):
        for i, item in enumerate([result('SC_CLEAR'), result('SC_UNCERTAIN'), {**result(), 'Response': result()['Response'] + '\nextra'}, {**result(), 'Progress': 'Failed'}, {**result(), 'Response': result()['Response'].replace('Lane boundaries disappear behind dense fog.', 'none established')}]):
            item['Id'] = 'summary-' + str(i)
            request_id = self.preview()
            with patch('scene_contracts.operator.Gateway') as gateway:
                self.op.import_result(request_id, item)
            gateway.assert_not_called()
            self.assertNotEqual(self.store.case(1)['observations'][-1]['outcome'], 'positive')
        self.assertEqual(self.store.case(1)['alarm_checks'], [])

    def test_legacy_hack26_keeps_rule_bound_prompt(self):
        client = Mock()
        client.exact_item.return_value = {'Id': 'legacy-prompt', 'Text': 'legacy text'}
        client.request.return_value = {'Id': 'legacy-id', 'Progress': 'Completed', 'Response': 'DECISION: H26_DAMAGE_EVENT'}
        args = SimpleNamespace(title='legacy', start=START, end=END, camera_id=CAMERA, apply=True, max_wait=1, output_dir=str(self.path))
        with redirect_stdout(io.StringIO()):
            hack26.command_run(client, args)
        self.assertEqual(client.request.call_args.args[2]['PromptId'], 'legacy-prompt')
        self.assertNotIn('PromptId', self.op.request(self.preview())['metadata']['payload'])

    def test_assessment_and_note_are_escaped_in_html(self):
        request_id = self.preview()
        item = result()
        item['Response'] = item['Response'].replace('Fog obscures distant vehicles.', '<img src=x onerror=alert(1)>')
        self.op.import_result(request_id, item)
        self.store.review(1, '<script>bad()</script>')
        ui = scene_web.Console(self.op, 'token')
        html = ui.case(1)
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script>bad', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('No native alarm association', html)
        self.assertIn('synthetic-summary', ui.request(request_id))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class HTTPTests(OperatorFixture):
    def test_http_preview_import_review_and_csrf(self):
        args = SimpleNamespace(db=str(self.path / 'cases.sqlite3'), camera_map=str(self.map), contracts_dir=str(DEFAULT_CONTRACTS), port=0)
        server = scene_web.server(args)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(lambda: thread.join(timeout=2))
        self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port)
        opener = build_opener(NoRedirect())

        def get(path):
            with opener.open(base + path) as response:
                return response.read().decode()

        def post(path, fields, expected=303, origin=None):
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            if origin:
                headers['Origin'] = origin
            req = Request(base + path, data=urlencode(fields).encode(), headers=headers)
            try:
                opener.open(req)
                self.fail('Expected redirect or rejection')
            except HTTPError as exc:
                self.assertEqual(exc.code, expected)
                return exc.headers.get('Location')

        self.assertIn('Review cases', get('/'))
        self.assertIn('Configure a responsibility', get('/contracts'))
        self.assertIn('Preview request', get('/analyze'))
        token = server.csrf
        with patch('scene_contracts.operator.Gateway') as gateway:
            post('/preview', {'csrf': 'wrong'}, 403)
            post('/preview', {'csrf': token}, 403, 'https://attacker.invalid')
            location = post('/preview', {'csrf': token, 'contract': 'roadway-visibility', 'camera': 'highway_traffic_overcast_weather', 'start': START, 'end': END})
            self.assertIn('Exact resulting prompt', get(location))
            request_id = location.split('/')[-1]
            post('/submit', {'csrf': token, 'id': request_id}, 400)
            post('/import', {'csrf': token, 'id': request_id, 'provenance': 'yes', 'result': json.dumps(result())})
            self.assertIn('synthetic-summary', get(location))
            post('/review', {'csrf': token, 'id': '1', 'note': 'Inspected original footage'})
            self.assertIn('Inspected original footage', get('/cases/1'))
            gateway.assert_not_called()
        location = post('/preview', {'csrf': token, 'contract': 'roadway-visibility', 'camera': 'highway_traffic_overcast_weather', 'start': START, 'end': END})
        request_id = location.split('/')[-1]
        client = Mock()
        client.request.side_effect = [{'Id': 'http-submission', 'Progress': 'Running'}, result('SC_CLEAR', 'http-submission')]
        with patch('scene_contracts.operator.Operator.client', return_value=client):
            post('/submit', {'csrf': token, 'id': request_id, 'approved': 'yes'})
            self.assertIn('Checking every 5 seconds', get(location))
            post('/submit', {'csrf': token, 'id': request_id, 'approved': 'yes'})
            post('/refresh', {'csrf': token, 'id': request_id})
        self.assertEqual([c.args[0] for c in client.request.call_args_list], ['POST', 'GET'])
        self.assertNotIn('PromptId', client.request.call_args_list[0].args[2])
        self.assertIn('http-submission', get(location))
        with self.assertRaises(HTTPError) as caught:
            opener.open(Request(base + '/', headers={'Host': 'attacker.invalid'}))
        self.assertEqual(caught.exception.code, 403)
