import {useEffect, useRef} from 'react';
import type {Case, Frame} from './types';

export const SAMPLE_TOLERANCE = 0.05;

export type Player = {t: number; playing: boolean; box: boolean; region: boolean; index: number};

export function sampleAt(c: Case, p: Player): Frame | null {
  if (c.kind === 'snapshots') return c.frames[p.index] ?? null;
  return c.frames.find(f => f.mediaTime !== null && Math.abs(f.mediaTime - p.t) <= SAMPLE_TOLERANCE) ?? null;
}

function polygonOf(c: Case): number[][] | null {
  const r = c.vision?.region;
  if (!r) return null;
  return Array.isArray(r) ? r : r.polygon;
}

export function Stage({c, p, sample, videoRef, onTime, onPlay, onEnd}: {
  c: Case; p: Player; sample: Frame | null; videoRef: React.RefObject<HTMLVideoElement | null>;
  onTime: (t: number) => void; onPlay: (playing: boolean) => void; onEnd: () => void;
}) {
  const raf = useRef(0);
  useEffect(() => {
    if (c.kind !== 'video' || !p.playing) return;
    const tick = () => { const v = videoRef.current; if (v) onTime(v.currentTime); raf.current = requestAnimationFrame(tick); };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [c.kind, p.playing, onTime, videoRef]);
  const polygon = polygonOf(c);
  const box = sample?.box;
  const aspect = '832 / 480';
  return (
    <div className="stage" style={{aspectRatio: aspect}}>
      {c.kind === 'video' && c.video
        ? <video ref={videoRef} src={c.video.url} muted playsInline preload="auto" aria-label={`Recording from ${c.title}`}
            onPlay={() => onPlay(true)} onPause={() => onPlay(false)} onEnded={onEnd} />
        : sample && <img src={sample.file} alt={`Snapshot at ${sample.timestamp}`} />}
      <svg className="overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
        {p.region && polygon && <polygon points={polygon.map(q => q.join(',')).join(' ')} className="region" />}
        {p.box && box && <rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} className={sample?.near ? 'box near' : 'box'} />}
      </svg>
    </div>
  );
}
