"""Offline replay: real validated saved evidence plus labeled synthetic windows. No inference or dispatch."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adaptive_watch.evidence_api import EvidenceStore
from adaptive_watch import episodes


def replay(documents):
    reports=[]
    for name, windows in documents:
        db=sqlite3.connect(':memory:'); episodes.initialize(db)
        notifications=0
        for d in windows:
            before=db.execute('SELECT count(*) FROM episodes').fetchone()[0]
            episodes.ingest(db,d)
            notifications += db.execute('SELECT count(*) FROM episodes').fetchone()[0]-before
        count=db.execute('SELECT count(*) FROM observations').fetchone()[0]
        reports.append(dict(fixture=name,observations_ingested=len(windows),unique_observations=count,episodes_created=notifications,
            duplicate_incident_notifications_avoided=len(windows)-notifications,hafnia_requests_made=0,
            hafnia_requests_avoided=0,incidents_requiring_review=notifications,native_events_actually_verified=0))
        db.close()
    return reports


def fixtures(saved):
    repeats=[]
    for source in saved:
        for i in range(3):
            d=deepcopy(source)
            if i:
                d['syntheticFixture']=True; d['loopReset']=True
            repeats.append(d)
    windows=[]
    for source in saved:
        for i in range(3):
            d=deepcopy(source); d['syntheticFixture']=True
            d['manifestSha256']=episodes.digest(['synthetic',source['manifestSha256'],i])
            d['cvSha256']=episodes.digest(['synthetic',source['cvSha256'],i])
            # Grouping mechanics only: this approval is synthetic, never operational.
            d['geometryApproved']=True
            windows.append(d)
    return [('real_saved_baseline',saved),('synthetic_loop_reimports',repeats),('synthetic_compatible_windows',windows)]


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    # Copy the source database so replay does not mutate the operational queue.
    with tempfile.TemporaryDirectory() as temp:
        source=sqlite3.connect(a.source/'evidence.sqlite3');target=sqlite3.connect(Path(temp)/'evidence.sqlite3');source.backup(target);source.close();target.close()
        store=EvidenceStore(temp)
        try:
            saved=[]
            for row in store.index()['records']:
                for observation in store.get(row['id'])['observations']:
                    # Revalidate the real source before reporting it as saved evidence.
                    provenance=observation['provenance']
                    from adaptive_watch.incident import sha
                    for key,expected in [('joined','joinedSha256'),('cv','cvSha256'),('manifest','manifestSha256')]:
                        if sha(provenance[key]) != observation[expected]: raise ValueError('Saved artifact changed')
                    saved.append(observation)
            report=dict(scope='Offline replay; synthetic windows are not independent real-world evidence. No Hafnia calls scheduled, so avoided requests are unmeasured (reported zero).',fixtures=replay(fixtures(saved)))
            a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
        finally:store.close()

if __name__=='__main__':main()
