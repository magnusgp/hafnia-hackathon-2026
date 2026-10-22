from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from adaptive_watch.evaluation import Evaluation,parse_result
from adaptive_watch.tracking import Tracker


class ParseTests(unittest.TestCase):
    def test_failed_gateway_cannot_use_positive_response(self):
        value=parse_result(dict(Progress='Failed',LastError='Export failed',Response='{"outcome":"supported"}'))
        self.assertFalse(value['analysis_success'])
        self.assertEqual(value['reason'],'Export failed')

    def test_duplicate_keys_and_markdown_are_uncertain(self):
        for text in ('{"outcome":"supported","outcome":"not_observed"}', '```json\n{}\n```'):
            self.assertEqual(parse_result(dict(Progress='Completed',Response=text))['outcome'],'uncertain')

    def test_exact_schema(self):
        response=dict(outcome='supported',evidence='Person steps off platform',timing='8–10 seconds',limitations='Intent unknown')
        self.assertEqual(parse_result(dict(Progress='Completed',Response=json.dumps(response)))['outcome'],'supported')


class LedgerTests(unittest.TestCase):
    def test_ambiguous_post_is_claimed_and_never_repeated(self):
        class Gateway:
            calls=0
            def request(self,*args):
                self.calls+=1
                raise TimeoutError('Do not retry')
        with tempfile.TemporaryDirectory() as temp:
            start=(datetime.now(timezone.utc)-timedelta(minutes=5)).replace(microsecond=0)
            end=start+timedelta(seconds=13)
            camera='11111111-1111-1111-1111-111111111111'
            manifest=Path(temp)/'manifest.json'
            manifest.write_text(json.dumps(dict(camera_id=camera,requested_start_utc=start.isoformat(),requested_end_utc=end.isoformat())))
            e=Evaluation(Path(temp)/'eval')
            entry=dict(camera_id=camera,start=start.isoformat(),end=end.isoformat(),scene='person_on_railway_tracks',
                       prompt_version='v1',recording_manifest=str(manifest),continuity_review='no_loop_boundary')
            g=Gateway()
            with self.assertRaises(TimeoutError):
                e.submit(g,entry)
            with self.assertRaises(sqlite3.IntegrityError):
                e.submit(g,entry)
            self.assertEqual(g.calls,1)
            self.assertIn('Submission ambiguous',next((Path(temp)/'eval').glob('*.json')).read_text())
            e.db.close()


class TrackingTests(unittest.TestCase):
    def test_missing_detections_do_not_invent_zone_duration(self):
        tracker=Tracker(max_gap_s=1.1)
        zone=[[0,0],[1,0],[1,1],[0,1]]
        detection=dict(box=[0.2,0.2,0.3,0.4],score=0.9)
        tracker.update(0,[detection],zone)
        tracker.update(0.5,[detection],zone)
        tracker.update(1,[],zone)
        tracker.update(3,[detection],zone)
        tracks=tracker.measurements()
        self.assertEqual(len(tracks),2)
        self.assertEqual([t['observed_zone_s'] for t in tracks],[0.5,0])

    def test_zone_entry_is_bracket_not_exact_time(self):
        tracker=Tracker()
        zone=[[0.5,0],[1,0],[1,1],[0.5,1]]
        tracker.update(0,[dict(box=[0.35,0.1,0.45,0.3],score=0.9)],zone)
        tracker.update(0.5,[dict(box=[0.5,0.1,0.6,0.3],score=0.9)],zone)
        self.assertEqual(tracker.measurements()[0]['zone_entry_brackets_s'],[[0,0.5]])


class EvidenceTests(unittest.TestCase):
    def cv(self):
        return dict(source_manifest=dict(source='Get-Snapshot',camera_id='11111111-1111-1111-1111-111111111111',
            camera_name='railway',requested_start_utc='2026-10-22T11:00:00Z',requested_end_utc='2026-10-22T11:00:13Z'),
            observations=[dict(timestamp_utc='2026-10-22T11:00:00Z')],manifest_sha256='abc',limitations=[],tracks=[])

    def test_absent_hafnia_is_incomplete(self):
        from adaptive_watch.evidence import join_evidence
        record=join_evidence(self.cv())
        self.assertEqual(record['combined_decision'],'incomplete_evidence')
        self.assertIsNone(record['event_metadata'])

    def test_mismatched_recording_refused(self):
        from adaptive_watch.evidence import join_evidence
        with self.assertRaises(ValueError):
            join_evidence(self.cv(),dict(request=dict(VideoUris=['wrong']),summary=dict(Request={})))

    def test_failed_join_remains_failed_and_preserves_reason(self):
        from adaptive_watch.evidence import join_evidence
        from scene_contracts.gateway import video_uri
        cv=self.cv()
        m=cv['source_manifest']
        req=dict(Prompt='Exact inline prompt',VideoUris=[video_uri(m['camera_id'],
            datetime.fromisoformat(m['requested_start_utc'].replace('Z','+00:00')),
            datetime.fromisoformat(m['requested_end_utc'].replace('Z','+00:00')))])
        result=join_evidence(cv,dict(request=req,manifest_sha256='abc',summary=dict(
            Id='summary-1',Request=req,Progress='Failed',LastError='Transfer failed')))
        self.assertEqual(result['combined_decision'],'analysis_failed_or_pending')
        self.assertEqual(result['hafnia']['failure_reason'],'Transfer failed')


class TimestampTests(unittest.TestCase):
    def test_requested_end_is_not_decoded_end(self):
        try:
            from adaptive_watch.footage import timestamp_report
        except ImportError:
            self.skipTest('Requires optional numpy')
        start=datetime(2026,10,22,tzinfo=timezone.utc)
        end=start+timedelta(seconds=13)
        last=start+timedelta(seconds=12.5)
        r=timestamp_report([start,last],start,end)
        self.assertEqual(r['requested_end_utc'],'2026-10-22T00:00:13Z')
        self.assertEqual(r['decoded_last_minus_requested_end_s'],-0.5)
        self.assertIsNone(timestamp_report([start,last],start,None)['requested_end_utc'])
