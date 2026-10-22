"""Synthetic structural reproductions of saved response defects; no private text."""
import json
import unittest
from adaptive_watch.evaluation import parse_result

class RecoveryTest(unittest.TestCase):
    def response(self, text, state='Completed'):
        return parse_result(dict(Progress=state, Response=text))

    def text(self, timing=0.1):
        return json.dumps(dict(outcome='supported', evidence='Visible action.', timing=timing, limitations='Intent unknown.'))

    def test_saved_response_shapes(self):
        for timing in (0.1, 5.7, '0.0 - 12.5 seconds', 'unknown'):
            for fenced in (False, True):
                text = self.text(timing)
                if fenced: text = '```json\n'+text+'\n```'
                self.assertEqual(self.response(text)['outcome'], 'supported')

    def test_saved_unquoted_intervals_are_disclosed(self):
        for interval in ('5.7 to 11.5 seconds', '0.1 to 12.5 seconds'):
            raw = '```json\n'+self.text().replace('0.1', interval)+'\n```'
            result = self.response(raw)
            self.assertEqual(result['timing'], interval)
            self.assertIn('unquoted_timing_interval', result['normalizations'])

    def test_reject_ambiguous_or_invalid_content(self):
        for raw in (self.text()+' trailing', 'prefix '+self.text(), self.text().replace('"outcome":', '"outcome":"uncertain", "outcome":'),
                    self.text(True), self.text(float('nan')), self.text(-1), self.text([]), {}, self.text().replace('supported','invalid')):
            self.assertEqual(self.response(raw)['category'], 'malformed_format')

    def test_categories(self):
        self.assertEqual(self.response('')['category'], 'empty_response')
        self.assertEqual(self.response(None)['category'], 'empty_response')
        self.assertEqual(self.response('', 'Failed')['category'], 'gateway_inference_failure')
        self.assertEqual(self.response('', 'Running')['category'], 'pending')
        self.assertEqual(parse_result(None)['category'], 'transport_failure')
