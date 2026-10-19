import unittest
from datetime import datetime, timezone
from hack26 import extract_decision, format_utc, video_uri


class DecisionTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(extract_decision("DECISION: H26_DAMAGE_EVENT\nOBSERVATIONS: throw"), "H26_DAMAGE_EVENT")

    def test_explanation_token_not_trusted(self):
        self.assertIsNone(extract_decision("The possible value is H26_DAMAGE_EVENT"))

    def test_multiple_decisions_rejected(self):
        self.assertIsNone(extract_decision("DECISION: H26_DAMAGE_EVENT\nDECISION: H26_UNCERTAIN"))

    def test_unknown_rejected(self):
        self.assertIsNone(extract_decision("DECISION: H26_UNKNOWN"))

    def test_video_uri(self):
        a = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        b = datetime(2026, 10, 19, 12, 1, tzinfo=timezone.utc)
        uri = video_uri("e028f597-c64b-4f27-bb8d-08f5cd768e1c", a, b)
        self.assertIn("StartTime=2026-10-19T12:00:00Z", uri)
        self.assertIn("EndTime=2026-10-19T12:01:00Z", uri)
        self.assertEqual(format_utc(a), "2026-10-19T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
