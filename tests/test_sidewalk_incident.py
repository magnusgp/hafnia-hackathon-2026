from datetime import datetime
import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

from adaptive_watch.incident import SCOOTER, assemble, box_overlap, proposal, sha, spatial_config
from scene_contracts.gateway import video_uri
from scene_contracts.analytics_event import NS, validate


class IncidentTests(unittest.TestCase):
    def test_overlap_distinguishes_partial_box_from_clearance(self):
        self.assertAlmostEqual(box_overlap([0,0,1,1],[[0,0],[.4,0],[.4,1],[0,1]]),.4)
        self.assertEqual(box_overlap([.6,.6,.8,.8],[[0,0],[.4,0],[.4,.4],[0,.4]]),0)

    def test_separate_camera_approval_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'spatial.json'
            p.write_text(json.dumps(dict(camera_guid=SCOOTER, polygon=[[0,0],[1,0],[1,1]], approved=True)))
            with self.assertRaisesRegex(ValueError,'another camera'):
                spatial_config(p,'bin-camera')
            with self.assertRaisesRegex(ValueError,'Approval requires'):
                spatial_config(p,SCOOTER)

    def fixture(self, root, normalized=False):
        start='2026-10-23T10:00:00.000Z';end='2026-10-23T10:00:15.000Z'
        scene=dict(name='escooter_left_across_sidewalk',start=start,end=end,walkway=[[0,0],[1,0],[1,1],[0,1]])
        obs=[];frames=[]
        for n in range(6):
            name=f'{n}.jpg';(root/name).write_bytes(f'frame {n}'.encode())
            timestamp=f'2026-10-23T10:00:0{n}.000Z'
            frames.append(dict(file=name,timestamp_utc=timestamp,sha256=sha(root/name)))
            box=[.1,.1,.3,.3] if n==0 else [.4,.4,.6,.6]
            obs.append(dict(frames[-1],objects=[dict(box=box,box_walkway_overlap=1,score=.3)]))
        m=dict(camera_id=SCOOTER,camera_name=scene['name'],requested_start_utc=start,requested_end_utc=end,frames=frames)
        manifest=root/'manifest.json';manifest.write_text(json.dumps(m))
        cv=dict(scene=scene,manifest_sha256=sha(manifest),source_manifest=m,observations=obs,
                execution_device='cuda',execution_platform='Linux',host='p022-linux',limitations=[])
        (root/'cv.json').write_text(json.dumps(cv))
        req=dict(Prompt='Exact prompt',VideoUris=[video_uri(SCOOTER,datetime.fromisoformat(start.replace('Z','+00:00')),datetime.fromisoformat(end.replace('Z','+00:00')))])
        response=json.dumps(dict(outcome='supported',evidence='Object left on pavement.',timing=1,limitations='No intent established.'))
        if normalized: response='```json\n'+response+'\n```'
        record=dict(entry=dict(start=start,end=end,camera_id=SCOOTER,continuity_review='no_loop_boundary'),
                    manifest_sha256=sha(manifest),request=req,summary=dict(Id='actual-summary-id',Progress='Completed',Request=req,Response=response))
        (root/'record.json').write_text(json.dumps(record))
        spatial=dict(camera_guid=SCOOTER,polygon=scene['walkway'],approved=True,approved_by='test operator',approved_at=start,reference_frame_sha256=frames[0]['sha256'])
        (root/'spatial.json').write_text(json.dumps(spatial))
        return [root/'cv.json',manifest,root/'record.json',root/'spatial.json']

    def test_join_preview_and_source_times(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d)); e=assemble(*args)
            self.assertTrue(e['dispatch_review_ready']);self.assertFalse(e['automatic_dispatch_eligible'])
            payload,meta=proposal(e,'2026-10-23T11:00:00Z')
            self.assertTrue(validate(payload))
            xml=ET.fromstring(payload);ns={'m':NS}
            self.assertEqual(xml.findtext('m:EventHeader/m:Timestamp',namespaces=ns),'2026-10-23T10:00:01.000Z')
            self.assertIsNotNone(xml.find('m:ObjectList/m:Object/m:BoundingBox',ns))
            self.assertIn(b'Event created UTC 2026-10-23T11:00:00Z',payload)
            self.assertEqual(meta['xml_sha256'],hashlib.sha256(payload).hexdigest())

    def test_repaired_hafnia_never_unlocks_fresh_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            e=assemble(*self.fixture(Path(d),normalized=True))
            self.assertFalse(e['dispatch_review_ready'])
            self.assertEqual(e['hafnia'][0]['parsed']['outcome'],'supported')

    def test_join_rejects_frame_tampering_and_cpu_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.fixture(root)
            (root/'0.jpg').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'frame identity'):
                assemble(*args)
            args=self.fixture(root)
            cv=json.loads(args[0].read_text());cv['execution_device']='cpu';args[0].write_text(json.dumps(cv))
            with self.assertRaisesRegex(ValueError,'Linux CUDA'):
                assemble(*args)

    def test_request_interval_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d));record=json.loads(args[2].read_text())
            record['summary']['Request']['VideoUris']=['wrong-interval']
            args[2].write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,'request mismatch'):
                assemble(*args)

    def test_dispatch_blocks_duplicate_episode_after_unknown_outcome(self):
        spec=importlib.util.spec_from_file_location('sidewalk_command',Path(__file__).parents[1]/'scripts/adaptive_watch/incident.py')
        command=importlib.util.module_from_spec(spec);spec.loader.exec_module(command)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);args=self.fixture(root);e=assemble(*args)
            command.write(root/'joined.json',e)
            payload,meta=proposal(e,'2026-10-23T11:00:00Z')
            meta['evidence_sha256']=sha(root/'joined.json')
            (root/'proposal.xml').write_bytes(payload);command.write(root/'proposal.json',meta)
            a=SimpleNamespace(spatial=args[3],ledger=root/'ledger.sqlite3',target='127.0.0.1:9090')
            answers=['CONFIGURED','REVIEWED',meta['xml_sha256']]
            with patch.object(command,'send',return_value=dict(state='uncertain')) as sender, patch('builtins.input',side_effect=answers), patch('builtins.print'):
                command.dispatch(a,root)
                self.assertEqual(sender.call_count,1)
            with patch.object(command,'send') as sender, patch('builtins.input',side_effect=answers), patch('builtins.print'):
                with self.assertRaisesRegex(ValueError,'Episode already reserved'):
                    command.dispatch(a,root)
                sender.assert_not_called()

    def test_terminal_credentials_require_interactive_terminal(self):
        spec=importlib.util.spec_from_file_location('sidewalk_command',Path(__file__).parents[1]/'scripts/adaptive_watch/incident.py')
        command=importlib.util.module_from_spec(spec);spec.loader.exec_module(command)
        with patch.object(command.sys.stdin,'isatty',return_value=False), patch.object(command.getpass,'getpass') as password:
            with self.assertRaisesRegex(ValueError,'interactive terminal'):
                command.terminal_login(None)
            password.assert_not_called()


if __name__=='__main__':
    unittest.main()
