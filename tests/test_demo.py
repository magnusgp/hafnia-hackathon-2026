"""Offline replay isolation, durable decisions and source integrity."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adaptive_watch import episodes
from adaptive_watch.demo import Demo
from adaptive_watch.evidence_api import EvidenceStore
from adaptive_watch.incident import assemble, proposal, sha
import test_sidewalk_incident


class DemoTests(unittest.TestCase):
    def seed(self, root):
        evaluations = root / 'evaluations'
        evaluations.mkdir()
        store = EvidenceStore(root / 'real')
        try:
            for camera in ('escooter_left_across_sidewalk', 'bin_pushed_over_onto_sidewalk'):
                directory = root / camera
                directory.mkdir()
                args = test_sidewalk_incident.IncidentTests().fixture(directory, camera_name=camera)
                cv = json.loads(args[0].read_text())
                cv['scene']['walkway_approved'] = True
                args[0].write_text(json.dumps(cv))
                evidence = assemble(*args)
                evidence['schema_version'] = 1
                evidence.pop('spatial')
                joined = directory / 'joined.json'
                joined.write_text(json.dumps(evidence))
                (evaluations / (camera + '.json')).write_bytes(args[2].read_bytes())
                store.register(joined, args[0], args[1], evaluations)
        finally:
            store.close()
        return evaluations

    def test_replay_grouping_decisions_reset_and_no_external_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluations = self.seed(root)
            before = sha(root / 'real/evidence.sqlite3')
            with patch('scene_contracts.gateway.Gateway', side_effect=AssertionError('No gateway')) as gateway, \
                 patch('scene_contracts.analytics_event.send', side_effect=AssertionError('No native send')) as sender, \
                 patch('adaptive_watch.evaluation.Evaluation.submit', side_effect=AssertionError('No inference')) as inference:
                demo = Demo(root / 'demo', root / 'real', evaluations)
                store = EvidenceStore(demo.active())
                for cursor in range(6):
                    demo.advance(store.db, cursor)
                records = store.index()['records']
                self.assertEqual(len(records), 2)
                self.assertEqual([r['observationCount'] for r in records], [3, 3])
                incident = store.get(records[0]['id'])
                self.assertEqual(incident['independentObservationCount'], 0)
                self.assertFalse(incident['dispatchReviewReady'])
                ids = sorted(o['observationId'] for o in incident['observations'])
                episodes.decide(store.db, incident['id'], 'review_required', 'Review complete', ids)
                episodes.decide(store.db, incident['id'], 'dismiss', 'Reviewed saved evidence', ids)
                old = demo.active()
                store.close()
                store = EvidenceStore(old)
                self.assertEqual(store.get(incident['id'])['state'], 'dismissed')
                self.assertEqual(len(store.get(incident['id'])['decisions']), 2)
                store.close()
                demo.reset()
                store = EvidenceStore(demo.active())
                self.assertEqual(store.index()['records'], [])
                store.close()
                self.assertTrue((old / 'evidence.sqlite3').exists())
                gateway.assert_not_called()
                sender.assert_not_called()
                inference.assert_not_called()
            self.assertEqual(before, sha(root / 'real/evidence.sqlite3'))
            with self.assertRaisesRegex(ValueError, 'separate'):
                Demo(root / 'real', root / 'real', evaluations)

    def test_seed_rejects_changed_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluations = self.seed(root)
            (root / 'escooter_left_across_sidewalk/0.jpg').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'frame identity'):
                Demo(root / 'demo', root / 'real', evaluations)

    def test_dismiss_during_playback_keeps_repeats_in_same_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            demo = Demo(root / 'demo', root / 'real', self.seed(root))
            store = EvidenceStore(demo.active())
            demo.advance(store.db, 0)
            incident = store.get(store.index()['records'][0]['id'])
            episodes.decide(store.db, incident['id'], 'dismiss', '',
                            sorted(o['observationId'] for o in incident['observations']))
            for cursor in range(1, 6):
                demo.advance(store.db, cursor)
            self.assertEqual(len(store.index()['records']), 2)
            saved = store.get(incident['id'])
            self.assertEqual(saved['state'], 'dismissed')
            self.assertEqual(saved['observationCount'], 3)
            store.close()

    def test_open_investigation_stale_evidence_never_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            demo = Demo(root / 'demo', root / 'real', self.seed(root))
            store = EvidenceStore(demo.active())
            try:
                demo.advance(store.db, 0)
                incident = store.get(store.index()['records'][0]['id'])
                old_ids = sorted(o['observationId'] for o in incident['observations'])
                demo.advance(store.db, 1)
                for action in ('review_required', 'dismiss', 'request_escalation'):
                    with self.assertRaisesRegex(ValueError, 'Evidence changed'):
                        episodes.decide(store.db, incident['id'], action, 'Preserve note', old_ids)
                updated = store.get(incident['id'])
                self.assertEqual(updated['decisions'], [])
                self.assertEqual(updated['approvalRequests'], [])
                self.assertEqual(updated['state'], 'candidate')
                self.assertEqual(updated['observationCount'], 2)
                ids = sorted(o['observationId'] for o in updated['observations'])
                episodes.decide(store.db, incident['id'], 'review_required', 'Preserve note', ids)
                self.assertEqual(store.get(incident['id'])['decisions'][0]['evidence'], ids)
            finally:
                store.close()

    def test_native_proposal_uses_measured_object(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = assemble(*test_sidewalk_incident.IncidentTests().fixture(Path(directory)))
            run = evidence['measurements']['qualifying_runs'][0]
            row = next(r for r in evidence['local_cv']['observations'] if r['timestamp_utc'] == run['first'])
            row['objects'].append(dict(box=[0, 0, 1, 1], score=.99))
            _, meta = proposal(evidence)
            selected = next(r['object'] for r in evidence['measurements']['trajectory'] if r['timestamp_utc'] == run['first'])
            self.assertEqual(meta['box'], selected['box'])
            self.assertNotEqual(meta['box'], [0, 0, 1, 1])
