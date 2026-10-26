import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from adaptive_watch import episodes

class EpisodeTests(unittest.TestCase):
    def fixture(self):
        return dict(id='a'*24,title='Obstruction',camera='scooter',cameraGuid='camera',capability='persistent_object',objectClass='scooter',
            interval=['2026-10-26T10:00:00Z','2026-10-26T10:00:10Z'],manifestSha256='m',cvSha256='c',joinedSha256='j',geometryApproved=True,
            polygon=[[0,0],[1,0],[1,1]],frames=[dict(box=[.1,.1,.3,.3])],hafnia=[dict(summary_id='one')])
    def test_persistence_assessments_decisions_and_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'episodes.db';db=sqlite3.connect(path);episodes.initialize(db)
            d=self.fixture();eid=episodes.ingest(db,d)
            d['hafnia']=[dict(summary_id='two')];self.assertEqual(episodes.ingest(db,d),eid)
            v=episodes.view(db,eid);self.assertEqual(len(v['hafnia']),2);self.assertEqual(v['observationCount'],1)
            evidence=[o['observationId'] for o in v['observations']]
            with self.assertRaises(ValueError):episodes.decide(db,eid,'dismiss',evidence=[])
            episodes.decide(db,eid,'review_required',evidence=evidence)
            episodes.decide(db,eid,'request_escalation','Review complete',evidence)
            episodes.record_dispatch(db,eid,'j',dict(state='accepted'),'xml')
            db.close();db=sqlite3.connect(path);v=episodes.view(db,eid)
            self.assertEqual(v['state'],'escalated');self.assertEqual(len(v['decisions']),2)
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM decisions')
            db.close()
    def test_grouping_boundaries_and_loop(self):
        a=self.fixture();a['location']=[.1,.1,.3,.3]
        b=deepcopy(a);b['manifestSha256']='next';b['interval']=['2026-10-26T10:00:10Z','2026-10-26T10:00:20Z'];b['cvSha256']='next'
        self.assertTrue(episodes.compatible(a,b))
        for key,value in [('cameraGuid','other'),('capability','other'),('objectClass','bin'),('location',[.6,.6,.8,.8]),('geometryApproved',False),('loopReset',True),('conflict',True),('interval',['2026-10-26T10:01:00Z','2026-10-26T10:01:10Z'])]:
            with self.subTest(key=key):
                bad=deepcopy(b);bad[key]=value;self.assertFalse(episodes.compatible(a,bad))
        db=sqlite3.connect(':memory:');episodes.initialize(db);eid=episodes.ingest(db,a)
        a['loopReset']=True;self.assertEqual(episodes.ingest(db,a),eid)
        evidence=[o['observationId'] for o in episodes.view(db,eid)['observations']]
        episodes.decide(db,eid,'resolution_unverified',evidence=evidence)
        self.assertEqual(episodes.view(db,eid)['state'],'resolution_unverified');db.close()

    def test_replay_counts_and_location_anchor(self):
        from scripts.adaptive_watch.replay_episodes import replay, fixtures
        saved=[self.fixture()]
        reports=replay(fixtures(saved))
        self.assertEqual([(r['observations_ingested'],r['unique_observations'],r['episodes_created']) for r in reports],[(1,1,1),(3,1,1),(3,3,1)])
        db=sqlite3.connect(':memory:');episodes.initialize(db);a=self.fixture();eid=episodes.ingest(db,a)
        b=deepcopy(a);b['manifestSha256']='second';b['cvSha256']='second';b['frames'][0]['box']=[.12,.12,.32,.32]
        self.assertEqual(episodes.ingest(db,b),eid)
        c=deepcopy(b);c['manifestSha256']='third';c['cvSha256']='third';c['frames'][0]['box']=[.14,.14,.34,.34]
        self.assertNotEqual(episodes.ingest(db,c),eid)
        db.close()

    def test_native_reservation_freezes_browser_decisions(self):
        db=sqlite3.connect(':memory:');episodes.initialize(db);eid=episodes.ingest(db,self.fixture())
        evidence=[o['observationId'] for o in episodes.view(db,eid)['observations']]
        episodes.decide(db,eid,'request_escalation',evidence=evidence)
        episodes.reserve_dispatch(db,eid,'j','xml')
        with self.assertRaises(ValueError):episodes.decide(db,eid,'dismiss',evidence=evidence)
        with self.assertRaises(sqlite3.IntegrityError):episodes.reserve_dispatch(db,eid,'j','xml')
        self.assertEqual(episodes.view(db,eid)['state'],'review_required');db.close()
