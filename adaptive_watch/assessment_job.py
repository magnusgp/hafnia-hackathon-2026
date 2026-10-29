"""Browser-initiated "New assessment": record, check, detect, ask Hafnia once, compare.

Every external effect (XProtect acquisition, MP4 encoding, Linux GPU vision, Hafnia) sits behind an
injectable Runner so tests use fakes. A job is one SQLite row; the Hafnia request is claimed before
it is sent and never sent twice. The gateway password never enters this module: a launcher builds an
authenticated gateway and passes only a factory. Nothing here sends a native XProtect event.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import statistics
import subprocess
import sys
import threading
import uuid

from adaptive_watch.evaluation import MAX_CLIP_S, MIN_CLIP_S, Evaluation, check_clip
from adaptive_watch.negative_review import digest, distance, read, sha
from adaptive_watch.tracking import foot

ROOT = Path(__file__).resolve().parents[1]
CAMERA = 'person_on_railway_tracks'
TITLE = 'Station platform'
WINDOW_S, MARGIN_S = 15, 90
REGION = dict(polygon=[[0.25, 0.32], [1.0, 0.67], [1.0, 1.0], [0.62, 1.0]], threshold=0)
NO_GATEWAY = ('This server was started without a Hafnia gateway session.',
              'Start it with scripts\\launch.ps1 and enter the gateway password once in that window.')
STAGES = [('acquisition', 'Record the camera interval'), ('continuity', 'Check the recording is continuous'),
          ('vision', 'Local person detection'), ('hafnia', 'Ask Hafnia'), ('matching', 'Compare the two answers')]
STATE_STAGE = dict(queued=0, acquiring=0, awaiting_continuity=1, cv_running=2, hafnia_submitting=3,
                   hafnia_waiting=3, matching=4)
TERMINAL = {'completed', 'failed'}
REFERENCE = 'runs/xprotect/person_on_railway_tracks_20261022T110339Z/manifest.json'  # clip starts at frame 0
LEAD_S, PHASE_MAX_AGE_S, CAL_SECONDS, CYCLE = 0.6, 6*3600, 32, 'loop-cycle.npz'
# The loop is visually seamless: the next walk-in already starts about 13.3 s into the 15 s cycle (measured on the
# 28 Oct recording), so a window must stop well before the restart instant, not at it.
TAIL_S = 2.0
NATIVE_EVENT = 'Adaptive Watch Review Required'
HANDOFF_NEGATIVE = ('Review exception: Hafnia reported no entry; independent person detection placed a person at the '
                    'platform edge from {trigger} UTC. Neither signal confirms entry. Review the footage.')
SSH_HOST, REMOTE_REPO, REMOTE_PY = 'ubuntu@p022-linux', '/home/ubuntu/hafnia-hackathon-2026', '.venv/bin/python'
RUNNER_REL = 'scripts/adaptive_watch/railway_cv.py'
TRACKER_REL = 'adaptive_watch/tracking.py'
EVIDENCE_LOST = 'Source files failed verification. Restore the original recording, response and vision output for this case.'


class StageError(ValueError):
    """A specific, user-facing failure. A ValueError subclass, so HTTP routes that catch ValueError already cover it."""
    def __init__(self, reason, next_step, resumable=False):
        super().__init__(reason)
        self.reason, self.next, self.resumable = reason, next_step, resumable


class Waiting(Exception):
    """Hafnia has not finished yet. The job stays pending; the request is polled, never resent."""


def iso(t):
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def hms(value):
    """HH:MM:SS.s (one decimal, UTC, no zone suffix) from an ISO timestamp."""
    t = parse(value).astimezone(timezone.utc)
    return f'{t:%H:%M:%S}.{t.microsecond//100000}'


_CACHE, _CACHE_LOCK = {}, threading.Lock()


def _signature(paths):
    return tuple((str(p), Path(p).stat().st_size, Path(p).stat().st_mtime_ns) for p in paths)


def _verified_once(key, paths, compute):
    """Run the expensive hash verification once per (key, size/mtime signature) of the files."""
    sig = _signature(paths)
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if hit and hit[0] == sig:
        return hit[1]
    value = compute()
    with _CACHE_LOCK:
        if len(_CACHE) > 64:
            _CACHE.clear()
        _CACHE[key] = (sig, value)
    return value


# -- interval and continuity (pure) ----------------------------------------------------------------
def choose_interval(sequences, now, phase=None, window=WINDOW_S, margin=MARGIN_S, hafnia=True):
    """Newest whole-second window ending at least `margin` s ago, inside one recording sequence.

    Without `phase`: a `window`-second window. With a calibrated loop `phase` (the camera replays one clip every
    `period` s, restarting at seam_utc + k*period): the longest whole-second window that starts just after a
    restart and ends TAIL_S before the next one. The clip is seamless, so the next cycle's walk-in begins before
    the restart instant; ending early keeps it out of the window.

    With `hafnia` (default) the window must be a length the gateway accepts (MIN_CLIP_S..MAX_CLIP_S), checked on the
    serialized timestamps. A window is never lengthened across a loop restart to reach the minimum; if the loop leaves
    too little clear time, the reason is raised before anything is claimed or sent.
    """
    latest = now.timestamp()-margin
    spans = [(math.ceil(parse(s['start_utc']).timestamp()), math.floor(parse(s['end_utc']).timestamp())) for s in sequences]
    if hafnia and not MIN_CLIP_S <= window <= MAX_CLIP_S:
        raise ValueError(f'The recording window must be {MIN_CLIP_S} to {MAX_CLIP_S} seconds (what Hafnia accepts)')

    def pair(start, end):
        s, e = iso(datetime.fromtimestamp(start, timezone.utc)), iso(datetime.fromtimestamp(end, timezone.utc))
        return (s, e) if not hafnia or MIN_CLIP_S <= (parse(e)-parse(s)).total_seconds() <= MAX_CLIP_S else None
    if phase:
        seam0, period = parse(phase['seam_utc']).timestamp(), float(phase['period'])
        top = math.floor((latest-seam0)/period)
        for k in range(top, top-1500, -1):
            seam = seam0+k*period
            start, end = math.ceil(seam+LEAD_S), math.floor(seam+period-TAIL_S)
            if hafnia:
                end = min(end, start+min(window, MAX_CLIP_S))  # shorten only, never past the loop-safe end
            chosen = pair(start, end) if end > start and end <= latest and any(a <= start and end <= b for a, b in spans) else None
            if chosen:
                return chosen
        clear = math.floor(seam0+(top)*period+period-TAIL_S)-math.ceil(seam0+top*period+LEAD_S)
        if hafnia and clear < MIN_CLIP_S:
            raise ValueError(f'This camera replays a {period:g} s loop. Keeping {TAIL_S:g} s clear of each restart leaves {clear} whole seconds, '
                             f'and Hafnia needs at least {MIN_CLIP_S}. Ortru will not stretch a recording across the restart, so this camera cannot be assessed.')
    else:
        for a, b in sorted(spans, key=lambda x: x[1], reverse=True):
            end = min(math.floor(latest), b)
            if end-window >= a:
                t = datetime.fromtimestamp(end, timezone.utc)
                return iso(t-timedelta(seconds=window)), iso(t)
    raise ValueError(f'The camera has no retained recording that covers a clean {window} second interval ending at least '
                     f'{margin} seconds ago. Check that it is recording, then try again in a minute.')


def flag_loop(diffs, times=None, ratio=6.0, floor=4.0, minimum=20, span=5):
    """Flag an isolated jump between consecutive frames: far above both the floor and its own neighbours.

    A loop restart is a single large step amid calm frames. Gradual ramps (encoder warm-up, a person crossing)
    raise the neighbours too and are not flagged.
    """
    if len(diffs) < minimum:
        return dict(flagged=False, checked=len(diffs), reason='too few frames to judge')
    best = None
    for i, value in enumerate(diffs):
        near = diffs[max(0, i-span):i]+diffs[i+1:i+1+span]
        score = value/max(statistics.median(near), .5)
        if best is None or score > best[0]:
            best = (score, i, value)
    score, peak, value = best
    return dict(flagged=value > floor and score > ratio, checked=len(diffs), median=round(statistics.median(diffs), 3),
                peak=round(value, 3), ratio=round(score, 1),
                atSeconds=round(times[peak+1], 2) if times else round((peak+1)/10, 2))


def check_manifest(manifest, guid, start, end, camera=CAMERA):
    manifest = Path(manifest)
    m = read(manifest)
    if (m.get('camera_id', '').lower() != guid.lower() or m.get('camera_name') != camera
            or parse(m['requested_start_utc']) != parse(start) or parse(m['requested_end_utc']) != parse(end)
            or 'mkv_export' not in m or len(m.get('frames', [])) < 2):
        raise StageError('The recording does not match the requested camera and interval', 'Start a new assessment.')
    paths = [manifest]+[(manifest.parent/f['file']).resolve() for f in m['frames']]

    def verify():
        for f, path in zip(m['frames'], paths[1:]):
            if not path.is_relative_to(manifest.parent.resolve()) or sha(path) != f['sha256']:
                raise StageError('A recorded snapshot is missing or changed', 'Start a new assessment.')
        return True
    try:
        _verified_once(('manifest', str(manifest), guid, start, end), paths, verify)
    except FileNotFoundError:
        raise StageError('A recorded snapshot is missing or changed', 'Start a new assessment.')
    return m


# -- default external effects ----------------------------------------------------------------------
def _run(args, timeout, cwd=None):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout, cwd=cwd)


def run_hafnia(job_dir, entry, gateway_factory, quota, on_state, timeout=600):
    """Claim, submit once, poll. A saved claim without an answer is polled or reported, never resent."""
    from scene_contracts.gateway import GatewayError
    ev = Evaluation(Path(job_dir)/'hafnia')
    try:
        rows = ev.db.execute('SELECT digest,summary_id FROM submissions').fetchall()
        if len(rows) > 1:
            raise StageError('More than one Hafnia request is recorded for this assessment',
                             'Reconcile in the Hafnia request history. Adaptive Watch will not send another.')
        gateway = gateway_factory()
        if rows:
            digest_, sid = rows[0]
            if not sid:
                raise StageError('A Hafnia request was started but its outcome is unknown',
                                 'Look it up in the Hafnia request history. Adaptive Watch will not send it again.')
            record = json.loads((Path(job_dir)/'hafnia'/(digest_+'.json')).read_text())
            if record['entry'] != entry:
                raise StageError('The saved Hafnia request differs from this assessment',
                                 'Keep the evidence and start a new assessment.')
            if not isinstance(record.get('summary'), dict) or record['summary'].get('Id') != sid:
                record['summary'] = dict(Id=sid)
        else:
            try:
                info = quota()
                used, allowed = info.get('DailySummaryCount'), info.get('DailySummaryQuota')
            except GatewayError:
                raise StageError('The Hafnia gateway cannot be reached', 'Check that the gateway service is running, then start again.')
            if isinstance(used, int) and isinstance(allowed, int) and used >= allowed:
                raise StageError(f"Today's Hafnia allowance is used up ({used} of {allowed})",
                                 'Try again after the allowance resets. Nothing was sent.')
            on_state('hafnia_submitting')
            try:
                digest_, record = ev.submit(gateway, entry)
            except GatewayError as exc:
                if re.search(r'HTTP 40[13]', str(exc)):
                    with ev.db:  # the gateway refused the session before accepting anything: release the claim
                        ev.db.execute('DELETE FROM submissions WHERE summary_id IS NULL')
                    raise StageError('The gateway rejected the session', 'Restart scripts\\launch.ps1 and enter the password again. Nothing was sent.')
                raise StageError('The Hafnia request may or may not have reached the gateway',
                                 'Look in the Hafnia request history. Adaptive Watch will not send it again.')
            except ValueError as exc:
                raise StageError(str(exc), 'Choose a different interval.')
            except Exception:
                raise StageError('The Hafnia request may or may not have reached the gateway',
                                 'Look in the Hafnia request history. Adaptive Watch will not send it again.')
        on_state('hafnia_waiting')
        try:
            record = ev.poll(gateway, digest_, record, timeout=timeout)
        except TimeoutError:
            raise Waiting()
        except GatewayError as exc:
            if re.search(r'HTTP 40[13]', str(exc)):
                raise StageError('The gateway rejected the session while waiting for the answer',
                                 'Restart scripts\\launch.ps1 and enter the password again. The same request will be polled, not resent.', True)
            raise StageError('The Hafnia gateway stopped answering', 'Restart the server. The same request will be polled, not resent.', True)
        if record.get('poll_outcome') == 'malformed_response' or 'parsed' not in record:
            raise StageError('The gateway returned an unreadable status', 'Restart the server. The same request will be polled, not resent.', True)
        parsed = record['parsed']
        if parsed['category'] in ('gateway_inference_failure', 'pending', 'transport_failure'):
            raise StageError('Hafnia could not analyse this recording: '+str(parsed.get('reason'))[:200], 'Start a new assessment.')
        return record
    finally:
        ev.db.close()


class Effects:
    """Real acquisition, encoding, GPU vision and Hafnia. Read-only against XProtect; no native sends."""
    def __init__(self, repo, deps=None, identity=None):
        self.repo = Path(repo)
        self.deps = Path(deps) if deps else (self.repo/'runs/tooling/pydeps' if (self.repo/'runs/tooling/pydeps').exists() else None)
        self.identity = Path(identity) if identity else Path.home()/'.ssh/hafnia_p022_linux'

    def _ps(self, *extra, camera=CAMERA):
        return ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', self.repo/'scripts/acquire_recording.ps1',
                '-CameraName', camera, *extra]

    def sequences(self, camera):
        r = _run(self._ps('-ListSequences', camera=camera), 180, self.repo)
        line = next((x for x in r.stdout.splitlines() if x.startswith('SEQUENCES_JSON:')), None)
        if r.returncode or line is None:
            raise StageError('XProtect did not list the recording', 'Check that the XProtect management server is running, then try again.')
        return json.loads(line.split(':', 1)[1])

    def acquire(self, camera, start, end, out, interval='0.5', mkv=True):
        seconds = int((parse(end)-parse(start)).total_seconds())
        r = _run(self._ps('-Start', start, '-Seconds', seconds, '-Interval', interval, *(['-Mkv'] if mkv else []), '-OutRoot', out, camera=camera), 600, self.repo)
        manifests = list(Path(out).glob('*/manifest.json'))
        if r.returncode or len(manifests) != 1:
            if 'not covered' in r.stdout+r.stderr:
                raise StageError('The interval is no longer inside the retained recording', 'Choose a different interval.')
            raise StageError('XProtect would not provide the recording', 'Check that the XProtect management server is running, then try again.')
        return manifests[0]

    def calibrate(self, sequences, now, out, camera=CAMERA, reference=REFERENCE):
        """Read a dense recent snapshot window (read only) and locate where the looping clip restarts."""
        import shutil
        from adaptive_watch.review_media import locate_seam
        start, end = choose_interval(sequences, now, window=CAL_SECONDS, margin=100, hafnia=False)
        manifest = self.acquire(camera, start, end, out, interval='0.1', mkv=False)
        try:
            return locate_seam(manifest, self.repo/reference, cycle_out=Path(out).parent/CYCLE) | dict(calibrated_window=[start, end], reference=reference, cycle=CYCLE)
        except FileNotFoundError:
            raise StageError('The reference clip needed to time the camera loop is missing', f'Restore {reference}.')
        except ValueError as exc:
            raise StageError('Could not time the camera loop: '+str(exc), 'Try again in a minute.')
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def check_window(self, manifest, offset, cycle):
        from adaptive_watch.review_media import verify_window
        try:
            return verify_window(manifest, cycle, offset)
        except FileNotFoundError:
            raise StageError('The saved camera loop cycle is missing', 'Start a new assessment; the loop will be measured again.')

    def encode(self, manifest, out):
        from adaptive_watch.review_media import prepare
        return prepare(manifest, out, self.deps)

    def run_cv(self, manifest, zone, out):
        manifest, zone, out = Path(manifest), Path(zone), Path(out)
        remote = '/tmp/aw-live-'+hashlib.sha256(str(out.parent).encode()).hexdigest()[:20]
        base = ['-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'ConnectTimeout=10', '-i', str(self.identity)]

        def ssh(cmd, timeout=900):
            r = _run(['ssh', *base, SSH_HOST, cmd], timeout)
            if r.returncode == 255:
                raise StageError('The Linux GPU host is unreachable over SSH', 'Check that p022-linux is running and reachable, then start again.')
            return r

        def scp(sources, target, cwd=None):
            r = _run(['scp', *base, *sources, target], 300, cwd)
            if r.returncode:
                raise StageError('Could not copy files to or from the Linux GPU host',
                                 'Check that p022-linux is reachable, then start again.' if r.returncode == 255 else 'Check disk space on p022-linux, then start again.')
        m = read(manifest)
        try:
            ssh(f'rm -rf {remote} && mkdir -p {remote}/rec {remote}/code/scripts/adaptive_watch {remote}/code/adaptive_watch', 60)
            # Ship the exact local runner and tracker rather than trusting the remote checkout; the output
            # report's runner/tracker/manifest hashes are verified against the local files afterwards.
            for rel in (RUNNER_REL, TRACKER_REL, 'adaptive_watch/footage.py', 'adaptive_watch/__init__.py'):
                scp([str(ROOT/rel)], f'{SSH_HOST}:{remote}/code/{rel}')
            scp([manifest.name, *[f['file'] for f in m['frames']]], f'{SSH_HOST}:{remote}/rec/', manifest.parent)
            scp([zone.name], f'{SSH_HOST}:{remote}/zone.json', zone.parent)
            r = ssh(f'cd {REMOTE_REPO} && {REMOTE_PY} {remote}/code/{RUNNER_REL} {remote}/rec/manifest.json --zone {remote}/zone.json --out {remote}/cv.json')
            if r.returncode:
                tail = (r.stderr.strip().splitlines() or ['no message'])[-1][:200]
                raise StageError('Local vision failed on the Linux GPU host: '+tail, 'Check the GPU on p022-linux, then start again.')
            scp([f'{SSH_HOST}:{remote}/cv.json'], str(out.name), out.parent)
        finally:
            try:
                ssh(f'rm -rf {remote}', 60)
            except Exception:
                pass
        return out

    def quota(self):
        from scene_contracts.gateway import Gateway
        return Gateway().request('GET', '/api/System/Information') or {}  # needs no login

    def hafnia(self, job_dir, entry, gateway_factory, on_state):
        return run_hafnia(job_dir, entry, gateway_factory, self.quota, on_state)


# -- completed live case (verified from the job directory) -----------------------------------------
def default_native():
    return dict(eventName=NATIVE_EVENT, state='not_configured', alarmId=None,
                detail='The review event and its camera alarm have not been set up in XProtect.')


def initial_state(d):
    return dict(status='review_required', region=read(Path(d)/'job.json')['region'], version=0, humanAnnotation=None, reviewed=False)


def verified_sources(d):
    """Hash every source once per size/mtime signature; a changed file forces a full re-verification."""
    d = Path(d)
    sources = read(d/'sources.json')

    def verify():
        for s in sources:
            if sha(d/s['path']) != s['sha256']:
                raise ValueError('Original evidence changed; this assessment is blocked')
        return sources
    try:
        return _verified_once(('sources', str(d)), [d/'sources.json']+[d/s['path'] for s in sources], verify)
    except FileNotFoundError:
        raise ValueError('Original evidence changed; this assessment is blocked')


def case_files(live_root, job_id):
    d = Path(live_root)/job_id
    verified_sources(d)
    manifest = Path(read(d/'job.json')['manifest'])
    m = read(d/manifest)
    return dict(frames=[(d/manifest).parent/f['file'] for f in m['frames']], video=d/'media/original.mp4')


def apply_action(state, body, trigger):
    """Local review decision on a live case; same rules as the saved railway review."""
    action, state = body.get('action'), json.loads(json.dumps(state))
    note = str(body.get('note', '')).strip()
    if len(note) > 2000:
        raise ValueError('Review note is too long')
    if action == 'configure_region':
        from adaptive_watch.negative_review import validate_region
        state.update(region=validate_region(body['region']), reviewed=False, humanAnnotation=None, status='review_required')
    elif action == 'review':
        state.update(reviewed=True, status='reviewing')
    elif action in {'dismiss', 'request_xprotect_review'}:
        if not state['reviewed'] or state['status'] != 'reviewing':
            raise ValueError('Review footage before making a decision')
        if body.get('footageReviewed') is not True:
            raise ValueError('Confirm that you reviewed the relevant footage')
        if action == 'request_xprotect_review' and not trigger:
            raise ValueError('The configured proximity condition is absent')
        annotation = body.get('annotation', 'not_verified')
        if annotation not in {'not_verified', 'entry_visible', 'entry_not_visible', 'uncertain'}:
            raise ValueError('Unknown human entry annotation')
        if annotation != 'not_verified' and not note:
            raise ValueError('Add a note describing the footage supporting your annotation')
        state['humanAnnotation'] = dict(value=annotation, note=note, at=datetime.now(timezone.utc).isoformat(),
                                        provenance='Local operator attestation; identity is not authenticated')
        state['status'] = 'dismissed' if action == 'dismiss' else 'xprotect_review_requested'
    else:
        raise ValueError('Unknown review action; native dispatch is unavailable')
    state['version'] += 1
    return state


def live_case(live_root, job_id, state=None, native=None):
    """Same schema as Casebook.railway_view, built only from the verified job directory."""
    d = Path(live_root)/job_id
    sources = verified_sources(d)
    job = read(d/'job.json')
    cid = 'live-'+job_id[:8]
    state = state or initial_state(d)
    m, cv, media = read(d/job['manifest']), read(d/'cv.json'), read(d/'media/media.json')
    record = read(d/'hafnia.json')
    if (cv['manifest_sha256'] != sha(d/job['manifest']) or len(cv['observations']) != len(m['frames'])
            or media['sourceMkvSha256'] != m['mkv_export']['sha256']
            or any(o['timestamp_utc'] != f['timestamp_utc'] for o, f in zip(cv['observations'], m['frames']))):
        raise ValueError('Vision output or video does not derive from the verified recording')
    polygon, threshold = state['region']['polygon'], state['region']['threshold']
    times = {s['index']: s['mediaTime'] for s in media['samples']}
    # Selected track: the one whose bounding-box foot first reaches the region (earliest sample, lowest id).
    dist = []
    for obs in cv['observations']:
        dist.append({o['track_id']: (distance(foot(o['box']), polygon), o['box']) for o in obs['objects']})
    first = min(((i, t) for i, row in enumerate(dist) for t, (dd, _) in row.items() if dd <= threshold), default=None)
    selected = first[1] if first else None
    frames = []
    for i, f in enumerate(m['frames']):
        dd, box = dist[i].get(selected, (None, None))
        frames.append(dict(index=i, timestamp=f['timestamp_utc'], mediaTime=times[i], box=box, distance=dd,
                           near=dd is not None and dd <= threshold, file=f'/api/cases/{cid}/frames/{i}'))
    trigger = next((f for f in frames if f['near']), None)
    parsed, summary = record['parsed'], record['summary']
    valid = parsed.get('category') == 'valid_model_decision'
    outcome = parsed.get('outcome') if valid else None
    answer, verdict = {'not_observed': ('No entry observed', 'negative'), 'supported': ('Entry observed', 'positive'),
                       'uncertain': ('Hafnia was unsure', 'uncertain')}.get(outcome, ('No usable answer', 'uncertain'))
    quote = parsed.get('evidence') if valid else str(parsed.get('reason') or summary.get('Response') or '')[:600]
    at = hms(trigger['timestamp']) if trigger else 'n/a'
    if trigger and verdict == 'negative':
        purpose, message = ('Hafnia answered no entry. Independent person detection had a person at the platform edge.',
                            HANDOFF_NEGATIVE.format(trigger=at))
    elif trigger and verdict == 'positive':
        purpose, message = ('Hafnia reported entry and person detection placed a person at the platform edge. Check the footage.',
                            f'Review request: Hafnia reported entry and independent person detection placed a person at the platform edge from {at} UTC. Review the footage.')
    elif trigger:
        purpose, message = ('Hafnia could not decide. Person detection placed a person at the platform edge.',
                            f'Review request: Hafnia was unsure; independent person detection placed a person at the platform edge from {at} UTC. Review the footage.')
    elif verdict == 'positive':
        purpose, message = ('Hafnia reported entry but person detection did not place anyone at the platform edge. The two signals disagree.',
                            'No handoff is prepared: person detection did not place a person at the platform edge.')
    else:
        purpose, message = ('No person reached the platform edge region in this interval. There is nothing to hand off.',
                            'No handoff is prepared: no person reached the platform edge region.')
    action_rev = digest([cid, digest(sources), state])
    return dict(
        id=cid, flagship=False, title=TITLE, camera=m['camera_name'], interval=job['interval'], purpose=purpose,
        revision=digest([action_rev, media['sha256']]), actionRevision=action_rev, kind='video', frames=frames,
        video=dict(url=f'/api/cases/{cid}/video', duration=media['duration'], fps=media['fps'],
                   origin=media['samples'][0]['timestamp'], sha256=media['sha256']),
        hafnia=dict(answer=answer, verdict=verdict, quote=quote, summaryId=summary['Id'], request=record['request']['Prompt']),
        vision=dict(label=f"Person detector, {cv['device']}", model=cv['model'], trackId=selected, region=state['region'],
                    trigger=trigger, regionStatus='draft region, not reviewed against this footage', samplesPerSecond=2,
                    tracks=len(cv['tracks']),
                    meaning=('A person was at the platform edge. This asks for a look. It does not say they entered.'
                             if trigger else 'No detected person reached the platform edge region. Detection can miss people.')),
        handoff=dict(event=NATIVE_EVENT, camera=TITLE, window=job['interval'], message=message,
                     alarm='Adaptive Watch review: station platform') if trigger else None,
        agent=None, state=state, native=native or default_native(),
        diagnostic=dict(note='Live assessment: one Hafnia request, no repeated-request diagnostic.'),
        provenance=dict(hashes=[dict(name=Path(s['path']).name, sha256=s['sha256']) for s in sources],
                        reference=dict(provenance='No calibration reference for a live assessment.')),
        limitations=['Person tracks are association hypotheses; identities can switch and detections can be missed.',
                     'The attention region is a draft that was not reviewed against this footage.',
                     'Hafnia answered one prompt once. Its answer is a model assessment, not a verified fact.',
                     continuity_note(live_root, job_id)])


def continuity_note(live_root, job_id):
    """Who confirmed continuity is stated only when the saved confirmation records it; never assumed to be a person."""
    saved = read(Path(live_root)/job_id/'continuity.json')
    who = saved.get('reviewer')
    if who:
        return f'The recording was confirmed as one continuous scene by: {who}.'
    return 'The browser confirmation that the recording plays as one continuous scene did not record who gave it.'


def completed_jobs(live_root):
    """Job ids of completed live assessments, oldest first. Read only."""
    db_path = Path(live_root)/'jobs.sqlite3'
    if not db_path.exists():
        return []
    db = sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True)
    try:
        return [r[0] for r in db.execute("SELECT id FROM jobs WHERE state='completed' ORDER BY created, id")]
    finally:
        db.close()


def resolve_case(live_root, case_id):
    ids = [j for j in completed_jobs(live_root) if 'live-'+j[:8] == case_id]
    if len(ids) != 1:
        raise KeyError(case_id)
    return ids[0]


# -- the job queue -----------------------------------------------------------------------------------
class Jobs:
    def __init__(self, repo, root, gateway_factory=None, runner=None, clock=None, resume=True):
        self.repo, self.live = Path(repo), Path(root)/'live'
        self.live.mkdir(parents=True, exist_ok=True)
        self.gateway_factory = gateway_factory
        self.runner = runner or Effects(self.repo)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock, self.threads = threading.RLock(), {}
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, camera TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
                state TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}', failed_stage TEXT, error TEXT, resumable INTEGER NOT NULL DEFAULT 0,
                case_id TEXT, created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(camera,start,end))''')
        if resume:
            self.resume()

    # storage
    def _db(self):
        class Conn:
            def __enter__(s):
                s.db = sqlite3.connect(self.live/'jobs.sqlite3', timeout=15, isolation_level=None)
                s.db.row_factory = sqlite3.Row
                return s.db

            def __exit__(s, *exc):
                s.db.close()
        return Conn()

    def _row(self, job_id):
        with self._db() as db:
            return db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()

    def _set(self, job_id, **cols):
        cols['updated'] = self.clock().isoformat()
        with self._db() as db:
            db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in cols)+' WHERE id=?', (*cols.values(), job_id))

    def _detail(self, job_id, stage, text, status=None):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT details FROM jobs WHERE id=?', (job_id,)).fetchone()
            details = json.loads(row['details'])
            details[stage] = dict(detail=text, status=status)
            db.execute('UPDATE jobs SET details=? WHERE id=?', (json.dumps(details), job_id))
            db.execute('COMMIT')

    def _fail(self, job_id, stage, reason, next_step, resumable=False):
        self._detail(job_id, stage, reason, 'failed')
        self._set(job_id, state='failed', failed_stage=stage, error=json.dumps(dict(reason=reason, next=next_step)),
                  resumable=int(resumable))

    def _dir(self, job_id):
        return self.live/job_id

    # public API
    def _guid(self):
        """The camera GUID comes only from the authorized local catalog, matched by exact name."""
        catalog = [c for c in json.loads((self.repo/'cameras.local.json').read_text(encoding='utf-8-sig')) if c['Name'] == CAMERA]
        if len(catalog) != 1:
            raise ValueError('The camera does not match the authorized local camera catalog.')
        return str(uuid.UUID(catalog[0]['Id']))

    def options(self):
        reason, next_step = NO_GATEWAY
        try:
            guid = self._guid()
        except (ValueError, OSError, KeyError):
            return dict(available=False, reason='The station platform camera is not in the local camera catalog.',
                        next='Run scripts\\list_cameras.ps1 and check cameras.local.json.', cameras=[])
        cameras = [dict(id=guid, name=CAMERA, title=TITLE)]
        if self.gateway_factory is None:
            return dict(available=False, reason=reason, next=next_step, cameras=cameras)
        return dict(available=True, cameras=cameras)

    def start(self, body):
        if not isinstance(body, dict):
            raise ValueError('Expected a request object')
        guid = self._guid()
        if str(body.get('cameraId', '')).lower() != guid.lower():
            raise ValueError('Only the station platform camera can be assessed.')
        if self.gateway_factory is None:
            raise ValueError(' '.join(NO_GATEWAY))
        with self.lock:
            with self._db() as db:  # a repeated click joins the running assessment, never starts another
                row = db.execute("SELECT id FROM jobs WHERE camera=? AND state NOT IN ('completed','failed') ORDER BY created DESC",
                                 (CAMERA,)).fetchone()
            if row:
                return self.get(row['id'])
            sequences = self.runner.sequences(CAMERA)
            phase = self._phase(sequences)
            start, end = choose_interval(sequences, self.clock(), phase)
            with self._db() as db:
                old = db.execute('SELECT id,state,resumable FROM jobs WHERE camera=? AND start=? AND end=?', (CAMERA, start, end)).fetchone()
            if old and old['state'] == 'failed' and not old['resumable']:
                if self._claims(old['id']):  # a Hafnia request exists for this interval: never allow another
                    return self.get(old['id'])
                with self._db() as db:  # failed before anything was sent: set it aside and allow a fresh attempt
                    db.execute("UPDATE jobs SET camera=camera||'#superseded-'||id WHERE id=?", (old['id'],))
            job_id = uuid.uuid4().hex
            now = self.clock().isoformat()
            with self._db() as db:
                db.execute('INSERT OR IGNORE INTO jobs(id,camera,start,end,state,created,updated) VALUES (?,?,?,?,?,?,?)',
                           (job_id, CAMERA, start, end, 'queued', now, now))
                job_id = db.execute('SELECT id FROM jobs WHERE camera=? AND start=? AND end=?', (CAMERA, start, end)).fetchone()['id']
            d = self._dir(job_id)
            if not (d/'job.json').exists():
                d.mkdir(parents=True, exist_ok=True)
                loop = dict(seamUtc=phase['seam_utc'], period=phase['period'],
                            offset=round((parse(start).timestamp()-parse(phase['seam_utc']).timestamp()) % float(phase['period']), 3))
                (d/'job.json').write_text(json.dumps(dict(id=job_id, camera=CAMERA, cameraGuid=guid, interval=[start, end],
                                                          region=REGION, loop=loop), indent=2), encoding='utf-8')
            self._kick(job_id)
            return self.get(job_id)

    def _claims(self, job_id):
        db_path = self._dir(job_id)/'hafnia'/'ledger.sqlite3'
        if not db_path.exists():
            return 0
        db = sqlite3.connect(db_path, timeout=15)
        try:
            return db.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
        finally:
            db.close()

    def _phase(self, sequences):
        """Calibrated loop phase, re-measured when missing or older than PHASE_MAX_AGE_S."""
        path = self.live/'phase.json'
        if path.exists():
            phase = read(path)
            if (self.clock()-parse(phase['calibrated_at'])).total_seconds() < PHASE_MAX_AGE_S:
                return phase
        phase = dict(self.runner.calibrate(sequences, self.clock(), self.live/'calibration'), calibrated_at=self.clock().isoformat())
        path.write_text(json.dumps(phase, indent=2), encoding='utf-8')
        return phase

    def _forget_phase(self):
        (self.live/'phase.json').unlink(missing_ok=True)
        (self.live/CYCLE).unlink(missing_ok=True)

    def get(self, job_id):
        row = self._row(job_id) if isinstance(job_id, str) and re.fullmatch(r'[0-9a-f]{32}', job_id) else None
        if row is None:
            return None
        details, state = json.loads(row['details']), row['state']
        cur = len(STAGES) if state == 'completed' else STATE_STAGE.get(state)
        if state == 'failed':
            cur = [k for k, _ in STAGES].index(row['failed_stage'])
        stages = []
        for i, (key, label) in enumerate(STAGES):
            status = 'done' if i < cur else ('running' if i == cur else 'waiting')
            extra = details.get(key) or {}
            if i == cur and state == 'awaiting_continuity':
                status = 'needs_you'
            if i == cur and state == 'failed':
                status = 'failed'
            detail = extra.get('detail')
            if i == cur and extra.get('status') in {'needs_you', 'failed'}:
                status = extra['status']
            if state in ('hafnia_submitting', 'hafnia_waiting') and i == cur and self.gateway_factory is None:
                status, detail = 'needs_you', ' '.join(NO_GATEWAY)
            stages.append(dict(key=key, label=label, status=status, **(dict(detail=detail) if detail else {})))
        if state == 'hafnia_waiting' and self.gateway_factory is not None:
            self._kick(row['id'])  # a poll that timed out resumes; the request is never resent
        d = self._dir(row['id'])
        out = dict(id=row['id'], state=state, stages=stages, error=json.loads(row['error']) if state == 'failed' else None,
                   caseId=('live-'+row['id'][:8]) if state == 'completed' else None, camera=TITLE,
                   interval=[row['start'], row['end']])
        if (d/'media/original.mp4').exists() and (d/'frame-diffs.json').exists():
            out.update(video=f"/api/jobs/{row['id']}/video", frameCount=len(read(d/'frame-diffs.json')['times']))
        return out

    def contact_frames(self, job_id):
        """Verified snapshot paths for the continuity check; only once the recording exists."""
        row = self._row(job_id) if isinstance(job_id, str) and re.fullmatch(r'[0-9a-f]{32}', job_id) else None
        manifests = list((self._dir(job_id)/'acquisition').glob('*/manifest.json')) if row else []
        if not manifests:
            raise KeyError(job_id)
        m = check_manifest(manifests[0], self._guid(), row['start'], row['end'])
        return [manifests[0].parent/f['file'] for f in m['frames']]

    def video_path(self, job_id):
        path = self._dir(job_id)/'media/original.mp4' if self._row(job_id) else None
        if not path or not path.exists():
            raise KeyError(job_id)
        return path

    def confirm_continuity(self, body):
        if not isinstance(body, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(body.get('id', ''))):
            raise ValueError('Unknown assessment')
        if body.get('reviewed') is not True:
            raise ValueError('Confirm that you watched the recording and it plays as one continuous scene.')
        job_id = body['id']
        row = self._row(job_id)
        if row is None:
            raise ValueError('Unknown assessment')
        if row['state'] != 'awaiting_continuity':
            raise ValueError('This assessment is not waiting for a continuity check.')
        manifest = next((self._dir(job_id)/'acquisition').glob('*/manifest.json'))
        (self._dir(job_id)/'continuity.json').write_text(json.dumps(dict(manifest_sha256=sha(manifest),
            reviewed_at=self.clock().isoformat(), reviewer='operator confirmation in the browser (identity not authenticated)')), encoding='utf-8')
        with self._db() as db:
            changed = db.execute("UPDATE jobs SET state='cv_running',updated=? WHERE id=? AND state='awaiting_continuity'",
                                 (self.clock().isoformat(), job_id)).rowcount
        if not changed:
            raise ValueError('This assessment is not waiting for a continuity check.')
        self._detail(job_id, 'continuity', 'Confirmed by you as one continuous scene.')
        self._kick(job_id)
        return self.get(job_id)

    def live_case(self, job_id, state=None, native=None):
        return live_case(self.live, job_id, state, native)

    def wait(self, job_id, timeout=60):
        t = self.threads.get(job_id)
        if t:
            t.join(timeout)

    # execution
    def resume(self):
        """After a restart pick up known jobs. Hafnia claims are polled, never resubmitted."""
        with self._db() as db:
            rows = db.execute("SELECT id,state,resumable FROM jobs WHERE state NOT IN ('completed','failed','awaiting_continuity') "
                              "OR (state='failed' AND resumable=1)").fetchall()
        for r in rows:
            if r['state'] == 'failed':
                self._set(r['id'], state='hafnia_waiting', failed_stage=None, error=None, resumable=0)
            self._kick(r['id'])

    def _kick(self, job_id):
        with self.lock:
            t = self.threads.get(job_id)
            if t and t.is_alive():
                return
            t = self.threads[job_id] = threading.Thread(target=self._guard, args=(job_id,), daemon=True)
            t.start()

    def _stage_of(self, state):
        return STAGES[STATE_STAGE[state]][0]

    def _guard(self, job_id):
        try:
            self._advance(job_id)
        except Waiting:
            pass
        except StageError as exc:
            self._fail(job_id, self._stage_of(self._row(job_id)['state']), exc.reason, exc.next, exc.resumable)
        except (ValueError, KeyError, OSError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
            stage = self._stage_of(self._row(job_id)['state'])
            text = str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__
            self._fail(job_id, stage, f'This step stopped unexpectedly: {text}', 'Start a new assessment. If it repeats, check the server window.')
        except Exception as exc:  # never leave a job silently unfinished
            self._fail(job_id, self._stage_of(self._row(job_id)['state']), f'This step stopped unexpectedly ({type(exc).__name__}).',
                       'Start a new assessment. If it repeats, check the server window.')

    def _advance(self, job_id):
        while True:
            state = self._row(job_id)['state']
            if state in ('queued', 'acquiring'):
                self._record(job_id)
            elif state == 'cv_running':
                self._vision(job_id)
            elif state in ('hafnia_submitting', 'hafnia_waiting'):
                if not self._hafnia(job_id):
                    return
            elif state == 'matching':
                self._match(job_id)
            else:
                return
            if self._row(job_id)['state'] in ('awaiting_continuity',) + tuple(TERMINAL):
                return

    def _record(self, job_id):
        row, d = self._row(job_id), self._dir(job_id)
        self._set(job_id, state='acquiring')
        self._detail(job_id, 'acquisition', 'Reading the recorded interval from XProtect (read only).')
        found = list((d/'acquisition').glob('*/manifest.json'))
        manifest = found[0] if found and 'mkv_export' in read(found[0]) else self.runner.acquire(CAMERA, row['start'], row['end'], d/'acquisition')
        m = check_manifest(manifest, self._guid(), row['start'], row['end'])
        window = self.runner.check_window(manifest, read(d/'job.json')['loop']['offset'], self.live/CYCLE)
        (d/'loop-window.json').write_text(json.dumps(window), encoding='utf-8')
        if not window.get('ok'):
            self._forget_phase()  # the next start measures the loop again
            self._detail(job_id, 'continuity', str(window.get('reason')), 'failed')
            return self._fail(job_id, 'continuity', 'The recording does not follow the expected 15 second loop timing',
                              'Start a new assessment. The loop timing will be measured again.')
        self._detail(job_id, 'acquisition', f"{len(m['frames'])} snapshots and the original recording saved. Preparing the video.")
        info, diffs = self.runner.encode(manifest, d/'media')
        native_times = [i/info['fps'] for i in range(len(diffs)+1)]
        (d/'frame-diffs.json').write_text(json.dumps(dict(times=native_times, diffs=diffs)), encoding='utf-8')
        (d/'job.json').write_text(json.dumps(read(d/'job.json') | dict(manifest=str(manifest.relative_to(d)).replace('\\', '/'))), encoding='utf-8')
        self._detail(job_id, 'acquisition', f"{len(m['frames'])} snapshots and a {info['duration']:.1f} s video saved and aligned.")
        check = flag_loop(diffs, native_times)
        (d/'loop-check.json').write_text(json.dumps(check), encoding='utf-8')
        if check['flagged']:
            self._detail(job_id, 'continuity', f"Automatic check: the picture jumps at {check['atSeconds']} s, {check['ratio']}x a typical frame change.", 'failed')
            return self._fail(job_id, 'continuity', 'The recording appears to restart partway through', 'Choose a different interval.')
        self._detail(job_id, 'continuity', f"Every snapshot matches the reference clip from {window['firstPosition']:.1f} s to {window['lastPosition']:.1f} s: "
                     'the window starts after the clip start and ends before it repeats. Watch it and confirm it is one continuous scene.', 'needs_you')
        self._set(job_id, state='awaiting_continuity')

    def _vision(self, job_id):
        d = self._dir(job_id)
        job = read(d/'job.json')
        manifest = d/job['manifest']
        cont = read(d/'continuity.json')
        if cont['manifest_sha256'] != sha(manifest):
            raise StageError('The recording changed after the continuity check', 'Start a new assessment.')
        self._detail(job_id, 'vision', 'Running person detection on the Linux GPU.')
        (d/'zone.json').write_text(json.dumps(dict(id='railway-track-zone-draft-v1', polygon=job['region']['polygon'])), encoding='utf-8')
        out = d/'cv.json'
        if not out.exists():
            self.runner.run_cv(manifest, d/'zone.json', out)
        cv = read(out)
        m = read(manifest)
        if (cv.get('manifest_sha256') != sha(manifest) or cv.get('runner_sha256') != sha(ROOT/RUNNER_REL)
                or cv.get('tracker_sha256') != sha(ROOT/TRACKER_REL) or len(cv.get('observations', [])) != len(m['frames'])):
            out.unlink()
            raise StageError('The vision output does not match this recording or the local code', 'Start a new assessment.')
        self._detail(job_id, 'vision', f"{cv['device']}: {cv['frames']} frames in {cv['processing_s']:.1f} s, {len(cv['tracks'])} person tracks.")
        self._set(job_id, state='hafnia_submitting')

    def _hafnia(self, job_id):
        """Return True when the answer is saved. Without a gateway session nothing is called."""
        if self.gateway_factory is None:
            return False
        d, row = self._dir(job_id), self._row(job_id)
        job = read(d/'job.json')
        entry = dict(scene=CAMERA, camera_id=job['cameraGuid'], start=row['start'], end=row['end'], prompt_version='v1',
                     continuity_review='no_loop_boundary', recording_manifest=str((d/job['manifest']).resolve()))
        cont = read(d/'continuity.json')
        if cont['manifest_sha256'] != sha(d/job['manifest']):
            raise StageError('The recording changed after the continuity check', 'Start a new assessment.')
        self._detail(job_id, 'hafnia', 'Sending one request to Hafnia, or reading the answer to the one already sent.')

        def on_state(state):
            self._set(job_id, state=state)
            self._detail(job_id, 'hafnia', 'Request sent once. Waiting for the answer.' if state == 'hafnia_waiting' else 'Sending one request to Hafnia.')
        record = self.runner.hafnia(d, entry, self.gateway_factory, on_state)
        (d/'hafnia.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        self._detail(job_id, 'hafnia', 'Hafnia answered: '+str(record['parsed'].get('outcome', 'no usable answer')).replace('_', ' ')+'.')
        self._set(job_id, state='matching')
        return True

    def _match(self, job_id):
        d = self._dir(job_id)
        job = read(d/'job.json')
        self._detail(job_id, 'matching', 'Comparing the person tracks with the platform edge region.')
        manifest = d/job['manifest']
        m = read(manifest)
        paths = [manifest, d/'continuity.json', d/'cv.json', d/'hafnia.json', d/'media/media.json', d/'media/original.mp4',
                 manifest.parent/m['mkv_export']['file'], *[manifest.parent/f['file'] for f in m['frames']]]
        (d/'sources.json').write_text(json.dumps([dict(path=str(p.relative_to(d)).replace('\\', '/'), sha256=sha(p)) for p in paths], indent=2), encoding='utf-8')
        case = live_case(self.live, job_id)
        n = case['vision']['trackId']
        self._detail(job_id, 'matching', f'Person track {n} first reaches the platform edge region at {hms(case["vision"]["trigger"]["timestamp"])} UTC.'
                     if n is not None else 'No person track reached the platform edge region.')
        self._set(job_id, state='completed', case_id=case['id'])
