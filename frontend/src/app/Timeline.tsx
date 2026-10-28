import type {Case} from './types';
import {clock, mediaOf, ms, utcAt} from './format';
import type {Player} from './Stage';

/** Three lanes on one clock. Detector samples are drawn only where they exist; gaps stay gaps. */
export function Timeline({c, p, seek}: {c: Case; p: Player; seek: (t: number) => void}) {
  if (c.kind !== 'video' || !c.video) return <SampleStrip c={c} p={p} seek={seek} />;
  const dur = c.video.duration, origin = c.video.origin;
  const x = (t: number) => `${(t / dur) * 100}%`;
  const trigger = c.vision?.trigger;
  const decisive = c.agent?.decisiveMoment;
  const phases = (c.agent?.phases ?? []).map(ph => ({...ph, a: mediaOf(ph.start, origin), b: Math.min(dur, mediaOf(ph.end, origin))}));
  const onClick = (e: React.MouseEvent<HTMLElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    seek(Math.max(0, Math.min(dur, ((e.clientX - r.left) / r.width) * dur)));
  };
  return (
    <div className="lanes">
      <div className="lane-labels" aria-hidden="true"><span>Hafnia</span><span>Local vision</span><span>Reviewed footage</span></div>
      <div className="lane-body" onClick={onClick}>
        <div className="lane"><div className="bar neutral" style={{left: 0, width: '100%'}}><span>Answered: {(c.hafnia.answer ?? 'see details').replace(/\.$/, '').toLowerCase()}</span></div></div>
        <div className="lane">
          {c.frames.map(f => f.mediaTime !== null && (
            <i key={f.index} className={`dot ${f.box ? (f.near ? 'near' : 'seen') : 'gap'}`} style={{left: x(f.mediaTime)}} title={`${clock(f.timestamp, 1)} ${f.box ? 'person detected' : 'no detection'}`} />
          ))}
          {trigger && trigger.mediaTime !== null && <span className="flag" style={{left: x(trigger.mediaTime)}}>At the edge {clock(trigger.timestamp, 1)}</span>}
        </div>
        <div className="lane">
          {phases.map(ph => <div key={ph.start} className={`bar ${ph.kind}`} style={{left: x(ph.a), width: `${((ph.b - ph.a) / dur) * 100}%`}}><span>{ph.label}</span></div>)}
        </div>
        <div className="playhead" style={{left: x(p.t)}} />
        <div className="ticks" aria-hidden="true">{Array.from({length: Math.floor(dur / 2) + 1}, (_, k) => k * 2).map(s => <span key={s} style={{left: x(s)}}>{clock(utcAt(s, origin))}</span>)}</div>
      </div>
      <input type="range" className="scrub" min={0} max={dur} step={1 / c.video.fps} value={p.t} onChange={e => seek(Number(e.target.value))}
        aria-label="Position in recording" aria-valuetext={`${clock(utcAt(p.t, origin), 1)} UTC`} />
      <span className="sr-only">{decisive ? `Decisive moment ${decisive.timestamp}` : ''}{trigger ? ` Detector trigger ${trigger.timestamp}` : ''}{ms(origin) ? '' : ''}</span>
    </div>
  );
}

function SampleStrip({c, p, seek}: {c: Case; p: Player; seek: (i: number) => void}) {
  return (
    <div className="lanes strip">
      <div className="lane-labels" aria-hidden="true"><span>Snapshots</span></div>
      <div className="lane-body">
        <div className="lane samples">
          {c.frames.map((f, i) => <button key={f.index} className={`snap ${i === p.index ? 'on' : ''} ${f.box ? 'seen' : ''}`}
            aria-label={`Snapshot ${i + 1} of ${c.frames.length}, ${f.timestamp}`} aria-current={i === p.index} onClick={() => seek(i)}>{i + 1}</button>)}
        </div>
      </div>
    </div>
  );
}
