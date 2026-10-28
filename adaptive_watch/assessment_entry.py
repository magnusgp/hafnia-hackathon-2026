"""Honest browser entry to the existing interactive analysis workflow.

Readiness checks never authenticate, submit, or retry an inference request. The
current CLI orchestration has no authenticated runtime handoff to an HTTP worker.
Retain blocked attempts separately from assessments and from inference ledgers.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from adaptive_watch.capabilities import cameras
from adaptive_watch.negative_review import read

BLOCKERS = [
    dict(code='authenticated_runtime_missing',
         message='The web service has no prepared authenticated Hafnia session. The existing analysis orchestrator requires an interactive operator sign-in.',
         action='Have the runtime maintainer prepare a server-side authenticated session handoff before enabling browser submission. Until then, use the existing supervised analysis workflow.'),
    dict(code='cuda_worker_handoff_missing',
         message='The existing Linux CUDA runner is invoked through the supervised workflow; no verified CUDA worker connection is attached to this web service.',
         action='The runtime maintainer must attach the existing Linux CUDA transport and pinned runner, with verified source transfer and returned-output validation.'),
    dict(code='recording_review_handoff_missing',
         message='Fresh recording acquisition and loop-continuity review are still supervised stages. Saved recording availability does not prove current XProtect coverage.',
         action='Acquire and verify the exact interval through the existing recording workflow, then review continuity and camera-specific geometry before analysis.')
]


class AssessmentEntry:
    def __init__(self, repo, root):
        self.repo, self.root = Path(repo), Path(root)

    def configurations(self):
        catalog = read(self.repo/'cameras.local.json')
        configurations = []
        for c in cameras(self.repo/'config/camera-capabilities.json'):
            if sum(item['Name'] == c['name'] and item['Id'].lower() == c['camera_guid'] for item in catalog) == 1:
                configurations.append(dict(id=c['camera_guid'],name=c['name'],configuration='Persistent sidewalk object',
                                           intervalSeconds=[12,17]))
        return dict(cameras=configurations,ready=False,blockers=BLOCKERS,
                    catalogNote='Existing authorized camera catalog; live recording coverage is checked only during acquisition.')

    def start(self, body):
        options = self.configurations()
        selected = next((c for c in options['cameras'] if c['id'] == body.get('cameraId')),None)
        if selected is None:
            raise ValueError('Select an existing authorized camera with a supported analysis configuration')
        bounds = []
        for key in ('start','end'):
            value = body.get(key)
            if not isinstance(value,str):
                raise ValueError('Choose the recording start and end in UTC')
            try:
                dt = datetime.fromisoformat(value.replace('Z','+00:00'))
            except ValueError:
                raise ValueError('Choose a valid recording interval') from None
            if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0 or dt.microsecond:
                raise ValueError('Recording bounds must be whole seconds in UTC')
            bounds.append(dt)
        now = datetime.now(timezone.utc)
        if not 12 <= (bounds[1]-bounds[0]).total_seconds() <= 17:
            raise ValueError('This backend supports recording intervals of 12–17 seconds')
        if bounds[1] > now or (now-bounds[0]).total_seconds() > 86400:
            raise ValueError('Choose a past recording interval within the last 24 hours; historical saved cases cannot be resubmitted')
        # Persist a real readiness result, never a fake analysis job or submission.
        result = dict(id=uuid4().hex,state='blocked',camera=selected['name'],interval=[d.isoformat() for d in bounds],
                      at=now.isoformat(),stage='Runtime readiness',blockers=options['blockers'],
                      inferenceSubmitted=False,recordingAcquired=False)
        self.root.mkdir(parents=True,exist_ok=True)
        db = sqlite3.connect(self.root/'assessment-readiness.sqlite3')
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, document TEXT NOT NULL)')
                db.execute('INSERT INTO attempts VALUES (?,?)',(result['id'],json.dumps(result)))
        finally:
            db.close()
        return result
