"""Real external effects for Ortru: XProtect (read only), MP4 encoding, Linux A10G vision, Hafnia.

Extends the proven Effects class with per-Watch camera selection, a camera snapshot for region drawing and loop-aware window
choice for cameras that replay a short clip. Nothing here changes XProtect or sends a native event.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

from adaptive_watch.assessment_job import Effects, StageError, iso, parse


class OrtruEffects(Effects):
    def phase(self, cfg, sequences, now, root):
        """Loop phase for cameras that replay a short clip, or None. Measured by `ortru.loops` and cached per camera."""
        from ortru.loops import window_phase
        return window_phase(self, cfg, sequences, now, Path(root))

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
