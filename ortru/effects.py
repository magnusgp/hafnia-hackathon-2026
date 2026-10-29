"""Real external effects for Ortru: XProtect (read only), MP4 encoding, Linux A10G vision, Hafnia.

Extends the proven Effects class with per-Watch camera selection, a camera snapshot for region drawing and loop-aware window
choice for cameras that replay a short clip. Nothing here changes XProtect or sends a native event.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys

from adaptive_watch.assessment_job import Effects, StageError, iso, parse


class OrtruEffects(Effects):
    def __init__(self, repo, deps=None, identity=None, private=None):
        super().__init__(repo, deps, identity)
        self.private = Path(private) if private else self.repo  # checkout that holds the private runs/ data (loop reference clips)
        if self.deps and str(self.deps.resolve()) not in sys.path:
            sys.path.insert(0, str(self.deps.resolve()))  # numpy, Pillow and av for loop alignment and encoding

    def _reference(self, cfg):
        return (cfg.get('source') or {}).get('loopReference')

    def encode(self, manifest, out):
        from adaptive_watch.review_media import prepare
        return prepare(manifest, out, self.deps, adaptive=True)

    def phase(self, cfg, sequences, now, root):
        """Loop phase for cameras that replay a short clip, or None.

        With a configured reference clip (a recording of the loop from its first frame) the restart instant is located by
        matching it, which also works when the loop is visually seamless. Without one, `ortru.loops` looks for visible jumps.
        """
        ref = self._reference(cfg)
        if not ref:
            from ortru.loops import window_phase
            return window_phase(self, cfg, sequences, now, Path(root))
        cam = cfg['camera']['id'].lower()
        path = Path(root)/'loops'/f'{cam}-reference.json'
        if path.exists():
            saved = json.loads(path.read_text(encoding='utf-8'))
            if (now-parse(saved['calibrated_at'])).total_seconds() < 6*3600 and saved.get('loop_reference') == ref:
                return saved
        out = Path(root)/'loops'/cam/'calibration'
        phase = dict(self.calibrate(sequences, now, out, camera=cfg['camera']['name'], reference=str(self.private/ref)), calibrated_at=now.isoformat(), loop_reference=ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(phase, indent=2), encoding='utf-8')
        return phase

    def verify_loop(self, cfg, manifest, start, root):
        """Check a recorded window against the saved loop cycle. None when the Watch has no loop reference."""
        if not self._reference(cfg):
            return None
        cam = cfg['camera']['id'].lower()
        phase = json.loads((Path(root)/'loops'/f'{cam}-reference.json').read_text(encoding='utf-8'))
        offset = (parse(start).timestamp()-parse(phase['seam_utc']).timestamp()) % float(phase['period'])
        return self.check_window(manifest, offset, Path(root)/'loops'/cam/'loop-cycle.npz')

    def snapshot(self, camera, out):
        """One recorded frame of the camera (the newest retained second), saved as JPEG. Read only."""
        sequences = self.sequences(camera)
        if not sequences:
            raise StageError('The camera has no retained recording to take a picture from', 'Check that the camera is recording.')
        end = parse(max(sequences, key=lambda s: s['end_utc'])['end_utc'])-timedelta(seconds=45)
        start = end-timedelta(seconds=2)
        if not any(parse(s['start_utc']) <= start and end <= parse(s['end_utc']) for s in sequences):
            raise StageError('The newest recording is too short for a snapshot', 'Try again in a minute.')
        tmp = Path(out).parent/('.snap-'+Path(out).stem)
        shutil.rmtree(tmp, ignore_errors=True)
        manifest = self.acquire(camera, iso(start), iso(end), tmp, interval='1', mkv=False)
        m = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(manifest).parent/m['frames'][0]['file'], out)
        shutil.rmtree(tmp, ignore_errors=True)
        return Path(out), m['frames'][0]['timestamp_utc']
