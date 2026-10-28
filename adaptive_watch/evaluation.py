"""Controlled inline Hafnia evaluation. No native event APIs or automatic resubmission."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from pathlib import Path
import sqlite3
import time

from scene_contracts.gateway import video_uri

SCENES = {
    'vehicle_breakdown_traffic_queue': 'a vehicle stops in a travel lane and traffic queues behind it; distinguish visible smoke or a driver exiting from a proven mechanical breakdown',
    'bin_pushed_over_onto_sidewalk': 'a person tips a wheeled bin over and leaves it lying on the sidewalk',
    'escooter_left_across_sidewalk': 'a person leaves an e-scooter lying across the sidewalk',
    'school_gate_break_in_night': 'a person manipulates a gate or its lock with a tool; do not assume successful entry or criminal intent',
    'person_on_railway_tracks': 'a person descends from the platform edge onto the railway track area or remains there; distinguish people standing on a platform',
    'graffiti_on_standing_train': 'a person applies paint or spray markings to the side of a standing train',
}


def prompt(scene, version):
    prefix = {'v1': 'Assess whether the following action is directly visible: ',
              'v2': 'Review the visible action sequence and decide whether this event is supported: '}[version]
    return (prefix + SCENES[scene] + '. Do not use camera names as evidence. '
            'Return only a JSON object with exactly these keys: '
            '"outcome" ("supported", "not_observed", or "uncertain"), '
            '"evidence" (short visible facts), "timing" (approximate seconds relative to clip start, or unknown), '
            '"limitations" (what this clip cannot establish). Do not infer intent or facts outside the clip.')


PARSER_VERSION = '2'


def parse_result(item):
    """Parse a complete response; record every compatibility normalization."""
    base = dict(outcome='uncertain', analysis_success=False, parser_version=PARSER_VERSION)
    if not isinstance(item, dict):
        return dict(base, category='transport_failure', reason='Invalid gateway envelope')
    state = item.get('Progress')
    if state != 'Completed':
        return dict(base, category='gateway_inference_failure' if state == 'Failed' else 'pending',
                    reason=item.get('LastError') or 'Gateway analysis did not complete')
    base['analysis_success'] = True  # gateway completion, not schema validity
    raw = item.get('Response')
    if raw is None or isinstance(raw, str) and not raw.strip():
        return dict(base, category='empty_response', reason='Completed request has no response text')
    if not isinstance(raw, str):
        return dict(base, category='malformed_format', reason='Response must be text')
    text = raw.strip()
    normalizations = []
    fence = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if fence:
        text = fence[1]
        normalizations.append('markdown_json_fence')
    # Recover only an unquoted numeric seconds interval in the timing field.
    # No substring JSON extraction, decision rewriting, or arbitrary JSON repair.
    interval = r'("timing"\s*:\s*)([0-9]+(?:\.[0-9]+)? to [0-9]+(?:\.[0-9]+)? seconds)(\s*,)'
    text, count = re.subn(interval, lambda m: m[1] + json.dumps(m[2]) + m[3], text)
    if count:
        normalizations.append('unquoted_timing_interval')
    try:
        def unique(pairs):
            obj = {}
            for k, v in pairs:
                if k in obj:
                    raise ValueError('Duplicate response key: ' + k)
                obj[k] = v
            return obj
        value = json.loads(text, object_pairs_hook=unique)
        if (not isinstance(value, dict) or set(value) != {'outcome','evidence','timing','limitations'}
                or not isinstance(value['outcome'], str)
                or value['outcome'] not in {'supported','not_observed','uncertain'}
                or any(not isinstance(value[k], str) or not value[k].strip() for k in ('evidence','limitations'))):
            raise ValueError('Invalid response schema')
        timing = value['timing']
        if not (isinstance(timing, str) and timing.strip() or
                type(timing) in (int, float) and math.isfinite(timing) and timing >= 0):
            raise ValueError('Invalid timing: expected text or finite nonnegative seconds')
        return dict(value, analysis_success=True, parser_version=PARSER_VERSION,
                    category='valid_model_decision', normalizations=normalizations,
                    reason='Model assessment only; operator verification required')
    except (ValueError, TypeError) as exc:
        return dict(base, category='malformed_format', normalizations=normalizations, reason=str(exc))


class Evaluation:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.db = sqlite3.connect(self.root/'ledger.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS submissions (digest TEXT PRIMARY KEY, record TEXT NOT NULL, summary_id TEXT, state TEXT NOT NULL)')
        self.db.commit()

    def submit(self, gateway, entry):
        start = datetime.fromisoformat(entry['start'].replace('Z','+00:00'))
        end = datetime.fromisoformat(entry['end'].replace('Z','+00:00'))
        if (start.tzinfo is None or end.tzinfo is None or not 12 <= (end-start).total_seconds() <= 17
                or end > datetime.now(timezone.utc) or start < datetime.now(timezone.utc)-timedelta(hours=24)):
            raise ValueError('Need a past 12–17 second UTC recording within the last 24 hours')
        if entry.get('continuity_review') != 'no_loop_boundary' or not entry.get('recording_manifest'):
            raise ValueError('Recording identity and manual loop continuity review required')
        manifest = json.loads(Path(entry['recording_manifest']).read_text(encoding='utf-8-sig'))
        if manifest['camera_id'].lower() != entry['camera_id'].lower():
            raise ValueError('Camera does not match recording manifest')
        ms = datetime.fromisoformat(manifest['requested_start_utc'].replace('Z','+00:00'))
        me = datetime.fromisoformat(manifest['requested_end_utc'].replace('Z','+00:00'))
        if not ms <= start < end <= me:
            raise ValueError('Interval outside acquired recording')
        payload = dict(Prompt=prompt(entry['scene'],entry['prompt_version']),
                       VideoUris=[video_uri(entry['camera_id'],start,end)])
        digest = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        record = dict(entry=entry,request=payload,request_sha256=digest,
                      manifest_sha256=hashlib.sha256(Path(entry['recording_manifest']).read_bytes()).hexdigest())
        # Commit a claim BEFORE the network mutation. A crash/timeout must block duplicate submission.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT COUNT(*) FROM submissions').fetchone()[0] >= 40:
                raise ValueError('Assignment cap of 40 attempted submissions reached')
            self.db.execute('INSERT INTO submissions VALUES (?,?,NULL,?)',(digest,json.dumps(record),'submission_ambiguous'))
        self._save(digest,record)
        try:
            result = gateway.request('POST','/api/Summaries',payload)
        except Exception as exc:
            record['failure_reason'] = 'Submission ambiguous: '+type(exc).__name__+'; reconcile history before any action'
            self._save(digest,record)
            raise
        if not isinstance(result,dict) or not result.get('Id'):
            raise ValueError('Ambiguous submission: reconcile gateway history; never resubmit')
        record['summary'] = result
        with self.db:
            self.db.execute('UPDATE submissions SET summary_id=?,state=? WHERE digest=?',(result['Id'],'submitted',digest))
        self._save(digest,record)
        return digest,record

    def _save(self,digest,record):
        path = self.root/(digest+'.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(record,indent=2),encoding='utf-8')
        temp.replace(path)

    def poll(self,gateway,digest,record,timeout=600):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            result = gateway.request('GET','/api/Summaries/'+record['summary']['Id'])
            if not isinstance(result, dict) or not isinstance(result.get('Progress'), str):
                record['poll_outcome'] = 'malformed_response'
                record['malformed_poll_response'] = result
                self._save(digest,record)
                return record
            record['summary'] = result
            if result.get('Progress') in {'Completed','Failed'}:
                record['parsed'] = parse_result(result)
                self._save(digest,record)
                with self.db:
                    self.db.execute('UPDATE submissions SET state=? WHERE digest=?',(result['Progress'],digest))
                return record
            self._save(digest,record)
            time.sleep(3)
        record['poll_outcome'] = 'timeout'
        self._save(digest,record)
        raise TimeoutError('Request remains pending; poll existing ID, do not resubmit')
