"""Agent-review ledger, provenance rules, case isolation and native-state reading."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from adaptive_watch.casebook import Casebook

REVIEW = dict(reviewer='Claude demo reviewer', provenance='AI visual review; not a human attestation.',
              decision='entry_visible', phases=[], observations=[])


class CasebookLedger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.release = root/'release'
        self.book = Casebook(root, root/'app', root/'railway', root/'responses', self.release)

    def tearDown(self):
        self.book.close()
        self.temp.cleanup()

    def test_review_needs_explicit_ai_provenance(self):
        with self.assertRaisesRegex(ValueError, 'AI provenance'):
            self.book.record_agent_review('railway', dict(REVIEW, provenance='Human attestation'), 'r1')
        with self.assertRaisesRegex(ValueError, 'AI provenance'):
            self.book.record_agent_review('railway', dict(REVIEW, reviewer='Operator'), 'r1')

    def test_review_is_append_only_and_latest_wins(self):
        self.book.record_agent_review('railway', REVIEW, 'r1')
        self.book.record_agent_review('railway', dict(REVIEW, decision='uncertain'), 'r1')
        self.assertEqual(self.book.agent_review('railway', 'r1')['decision'], 'uncertain')
        with self.assertRaises(sqlite3.DatabaseError):
            self.book.ws.db.execute("UPDATE agent_reviews SET case_id='gate'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.book.ws.db.execute('DELETE FROM agent_reviews')

    def test_review_of_changed_evidence_is_not_current(self):
        self.book.record_agent_review('railway', REVIEW, 'r1')
        self.assertTrue(self.book.agent_review('railway', 'r1')['currentSource'])
        self.assertFalse(self.book.agent_review('railway', 'r2')['currentSource'])

    def test_reviews_do_not_leak_between_cases(self):
        self.book.record_agent_review('railway', REVIEW, 'r1')
        self.assertIsNone(self.book.agent_review('gate', 'r1'))
        with self.assertRaises(KeyError):
            self.book.record_agent_review('unknown', REVIEW, 'r1')

    def test_native_state_is_never_inferred(self):
        self.assertEqual(self.book.native('railway')['state'], 'not_configured')
        (self.release/'native').mkdir(parents=True)
        (self.release/'native/status.json').write_text(json.dumps(dict(railway=dict(state='configured'))))
        self.assertEqual(self.book.native('railway')['state'], 'configured')
        self.assertEqual(self.book.native('gate')['state'], 'not_configured')
        self.assertIsNone(self.book.native('railway')['alarmId'])

    def test_status_labels(self):
        sent = dict(native=dict(state='sent'), state=dict(status='review_required'), flagship=True)
        self.assertEqual(Casebook.status(sent), 'Needs review')
        self.assertEqual(Casebook.status(dict(sent, state=dict(status='xprotect_review_requested'))), 'Review saved')
        self.assertEqual(Casebook.status(dict(sent, native=dict(state='alarm_verified'))), 'In XProtect')
        self.assertEqual(Casebook.status(dict(sent, flagship=False)), 'Evidence')


if __name__ == '__main__':
    unittest.main()
