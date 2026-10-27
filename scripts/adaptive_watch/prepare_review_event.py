"""Prepare local XML only. This command has no configuration or dispatch capability."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adaptive_watch.negative_review import ReviewStore, EVENT_NAME
from scene_contracts.analytics_event import build, dispatch_key


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('runs/negative-review'))
    a = p.parse_args()
    store = ReviewStore(a.root)
    try:
        record,_ = store.verified()
        view = store.view()
        key = dispatch_key(record['hafnia']['summaryId'],'negative-result-review',EVENT_NAME)
        payload = build(EVENT_NAME, record['cameraGuid'], record['frames'][0]['timestamp'],key,
            description='Human review required: negative Hafnia assessment with independent CV proximity evidence. Neither system automatically confirms railway entry.',
            start=record['interval'][0],end=record['interval'][1],vendor='Adaptive Watch')
        (a.root/'review-event-proposal.xml').write_bytes(payload)
        (a.root/'review-event-proposal.private.json').write_text(json.dumps(dict(eventName=EVENT_NAME,
            cameraGuid=record['cameraGuid'],interval=record['interval'],summaryId=record['hafnia']['summaryId'],
            reviewRevision=view['revision'],dispatchKey=key,xmlSha256=hashlib.sha256(payload).hexdigest(),
            configured=False,configurationAuthorized=False,dispatchAuthorized=False,
            nativeAlarmVerified=False,configuration='Proposed only; do not reuse the sidewalk event or alarm definition',
            nextSteps=['Obtain explicit authorization to configure this event and camera-specific alarm definition',
                       'Read back the actual configuration before enabling any send path',
                       'Obtain separate human approval for one exact payload and destination',
                       'Verify actual Smart Client alarm ID, source camera and playback of this original interval'],
            recordingAge='Historical saved interval; verify retained recording availability before any later native dispatch'),indent=2),encoding='utf-8')
        print('Prepared local XML and approval checklist. No event/alarm definition created; no event sent.')
    finally:
        store.close()


if __name__ == '__main__':
    main()
