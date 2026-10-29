"""The evidence archive: verified records from before Watches existed, read through a private copy.

Nothing here is a Watch result. The railway case and the first live assessment are authentic and source-verified; the
other three historical experiments are listed as evidence only. The archive is built from a copy of the operator state
(`scripts/ortru_prepare.py`), so the original review database, native status and ledgers are never opened for writing.
"""
from pathlib import Path
import sqlite3

from adaptive_watch.casebook import Casebook, DISPLAY
from adaptive_watch.negative_review import Conflict
from ortru import SCHEMA

NOTE = 'Recorded before Watches existed. It was not produced by a Watch configuration.'
SHOWN_AS_RECORDS = ('railway',)  # plus every completed live assessment


class Archive:
    def __init__(self, repo, root, railway, release, evaluations):
        self.args = (repo, root, railway, evaluations, release)
        self.root = Path(root)

    def book(self):
        return Casebook(*self.args)

    def available(self):
        return (self.root/'workspace.sqlite3').exists()

    def entries(self):
        """Archive listing: every verified historical record, labelled by what it is."""
        if not self.available():
            return dict(cases=[], unavailable=[])
        book = self.book()
        try:
            idx = book.index()
        finally:
            book.close()
        for c in idx['cases']:
            c['record'] = c['id'] == 'railway' or c['id'].startswith('live-')
            c['note'] = NOTE
        return idx

    def view(self, case_id):
        book = self.book()
        try:
            v = book.view(case_id)
        finally:
            book.close()
        return normalize(v)

    def video_path(self, case_id):
        book = self.book()
        try:
            if case_id == 'railway':
                return Path(self.args[4])/'media/railway/original.mp4'
            if case_id.startswith('live-'):
                return book.live_files(case_id)['video']
            raise KeyError(case_id)
        finally:
            book.close()

    def frame_path(self, case_id, i):
        book = self.book()
        try:
            if case_id.startswith('live-'):
                files = book.live_files(case_id)['frames']
                return files[i]
            v = book.view(case_id)
            if i >= len(v['frames']):
                raise KeyError(i)
            if case_id == 'railway':
                from adaptive_watch.negative_review import ReviewStore
                rs = ReviewStore(self.args[2])
                try:
                    record, _ = rs.verified()
                finally:
                    rs.close()
                return Path(record['frames'][i]['path'])
            return Path(book.ws.view(case_id, private=True)['frames'][i]['path'])
        finally:
            book.close()


def normalize(v):
    """One shape for every record. Native state is read-only here: transport acceptance and Smart Client verification apart."""
    cid = v['id']
    n = v.get('native') or {}
    verified = n.get('state') == 'alarm_verified'
    sent = n.get('state') in ('sent', 'alarm_verified')
    state = v.get('state') or {}
    vision = v.get('vision') or {}
    frames = v.get('frames') or []
    samples = [dict(index=f['index'], timestamp=f['timestamp'], mediaTime=f.get('mediaTime'), box=f.get('box'), distance=f.get('distance'),
                    near=bool(f.get('near'))) for f in frames]
    h = v.get('hafnia') or {}
    ann = state.get('humanAnnotation')
    return dict(
        schema=SCHEMA, id=cid, kind='archive', origin='archive', note=NOTE, title=v['title'], record=cid == 'railway' or cid.startswith('live-'),
        raised=bool(v.get('handoff')), watch=None, camera=dict(name=v['camera']), interval=v['interval'],
        at=(vision.get('trigger') or {}).get('timestamp') or v['interval'][0], reason=v['purpose'],
        policy=dict(kind='disagreement' if h.get('verdict') == 'negative' and vision.get('trigger') else 'recorded', raised=bool(v.get('handoff')),
                    label='Hafnia said no, local vision placed a person at the region' if h.get('verdict') == 'negative' and vision.get('trigger') else 'Recorded evidence'),
        hafnia=dict(answer=h.get('answer'), tone=h.get('verdict'), quote=h.get('quote'), summaryId=h.get('summaryId'), prompt=h.get('request'),
                    source='Hafnia VLM (AI footage review)', answers=h.get('answers')),
        vision=dict(detector='person_region_proximity' if vision.get('trigger') is not None or vision.get('trackId') else None, device=vision.get('label'),
                    model=vision.get('model'), region=vision.get('region'), samples=samples if vision else [], trackId=vision.get('trackId'),
                    trigger=vision.get('trigger'), samplesPerSecond=vision.get('samplesPerSecond'), meaning=vision.get('meaning')) if vision else None,
        video=dict(v['video'], url=f'/api/archive/{cid}/video') if v.get('video') else None,
        frames=[dict(index=f['index'], url=f"/api/archive/{cid}/frames/{f['index']}") for f in frames],
        decision=dict(status='review_requested' if state.get('status') in ('xprotect_review_requested', 'review_request_saved') else state.get('status'),
                      verdict=(ann or {}).get('value'), note=(ann or {}).get('note', ''), at=(ann or {}).get('at'), readOnly=True),
        native=dict(state='sent' if sent else 'not_sent', transport=dict(state='accepted' if sent else None, httpStatus=n.get('httpStatus'), at=n.get('sentAt')),
                    smartClient='verified' if verified else 'not_verified', alarm=n.get('alarmId'), detail=n.get('detail'), dispatchKey=n.get('dispatchKey'),
                    payloadSha256=n.get('payloadSha256')),
        handoff=v.get('handoff'), agent=v.get('agent'), limitations=v.get('limitations'),
        provenance=dict(hashes=(v.get('provenance') or {}).get('hashes') or [], reference=(v.get('provenance') or {}).get('reference')))
