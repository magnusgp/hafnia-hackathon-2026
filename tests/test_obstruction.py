import unittest
from adaptive_watch.obstruction import measure
from scripts.adaptive_watch.sidewalk_cv import utc


def row(t, x=.3, visible=True):
    return dict(timestamp_utc=f'2026-10-22T11:04:{t:06.3f}Z',objects=[] if not visible else
                [dict(box=[x,.6,x+.2,.8],box_walkway_overlap=.9,score=.5)])


class ObstructionTests(unittest.TestCase):
    def test_no_bridge_missing_observation(self):
        result=measure([row(30,.1),row(31),row(32),row(33,visible=False),row(34),row(35)])
        self.assertFalse(result['candidate'])

    def test_static_preexisting_bin_does_not_claim_new_onset(self):
        self.assertFalse(measure([row(t) for t in range(30,36)])['candidate'])

    def test_sampled_persistence_and_boundary(self):
        result=measure([row(30,.1)]+[row(t) for t in range(31,35)])
        self.assertEqual(result['qualifying_runs'][0]['sampled_span_s'],3)
        self.assertEqual(result['qualifying_runs'][0]['last'],'2026-10-22T11:04:34.000Z')

    def test_fractional_timestamp_boundary(self):
        self.assertLess(utc('2026-10-22T11:04:48Z'),utc('2026-10-22T11:04:48.009Z'))
        self.assertGreater(utc('2026-10-22T11:05:01.009Z'),utc('2026-10-22T11:05:01Z'))
