import {useCallback, useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import '@fontsource/space-grotesk/500.css';
import '@fontsource/space-grotesk/600.css';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/ibm-plex-mono/400.css';
import './app.css';
import {api} from './app/api';
import {Brief} from './app/Brief';
import {Decision, Details, NewAssessment, SendNative} from './app/Dialogs';
import {clock, utcAt} from './app/format';
import {Stage, sampleAt, type Player} from './app/Stage';
import {Timeline} from './app/Timeline';
import type {Assessment, Case, Summary} from './app/types';

const hashId = () => location.hash.replace(/^#\/?/, '') || '';

function Investigation({c, onChange}: {c: Case; onChange: (c: Case) => void}) {
  const video = useRef<HTMLVideoElement>(null);
  const stopAt = useRef<number | null>(null);
  const trigger = c.vision?.trigger ?? null;
  const decisive = c.agent?.decisiveMoment ?? null;
  const first = c.kind === 'video' ? (trigger?.mediaTime ?? 0) : 0;
  const [p, setP] = useState<Player>({t: first, playing: false, box: true, region: true, index: 0});
  const [dialog, setDialog] = useState<null | 'request' | 'dismiss' | 'details' | 'send'>(null);

  // Open at the decisive part of the recording, never at the first sample.
  useEffect(() => {
    setP({t: first, playing: false, box: true, region: true, index: 0});
    const v = video.current;
    if (!v) return;
    const set = () => { v.currentTime = first; };
    if (v.readyState >= 1) set(); else v.addEventListener('loadedmetadata', set, {once: true});
    return () => v.removeEventListener('loadedmetadata', set);
  }, [c.id, first]);

  const seek = useCallback((t: number) => {
    stopAt.current = null;
    const v = video.current;
    if (c.kind === 'video') { if (v) v.currentTime = t; setP(q => ({...q, t})); }
    else setP(q => ({...q, index: Math.max(0, Math.min(c.frames.length - 1, Math.round(t)))}));
  }, [c.kind, c.frames.length]);
  const onTime = useCallback((t: number) => {
    setP(q => ({...q, t}));
    if (stopAt.current !== null && t >= stopAt.current) { video.current?.pause(); stopAt.current = null; }
  }, []);
  const toggle = () => { const v = video.current; if (!v) return; if (v.paused) { stopAt.current = null; void v.play(); } else v.pause(); };
  const watch = () => {
    const v = video.current; if (!v || !trigger || trigger.mediaTime === null) return;
    v.currentTime = trigger.mediaTime; stopAt.current = (decisive?.mediaTime ?? trigger.mediaTime + 4) + 0.9; void v.play();
  };
  const samples = c.frames.filter(f => f.mediaTime !== null).map(f => f.mediaTime as number);
  const step = (dir: 1 | -1) => {
    if (c.kind === 'snapshots') return seek(p.index + dir);
    const t = dir > 0 ? samples.find(s => s > p.t + 0.001) : [...samples].reverse().find(s => s < p.t - 0.001);
    if (t !== undefined) seek(t);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest('input, select, textarea, dialog')) return;
    if (e.key === ' ' && c.kind === 'video') { e.preventDefault(); toggle(); }
    else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault(); const dir = e.key === 'ArrowRight' ? 1 : -1;
      if (e.shiftKey || c.kind === 'snapshots') step(dir); else seek(Math.max(0, Math.min(c.video!.duration, p.t + dir * 0.1)));
    } else if (e.key.toLowerCase() === 'd' && decisive) seek(decisive.mediaTime);
  };
  const sample = sampleAt(c, p);
  const origin = c.video?.origin;
  const readout = c.kind === 'video' && origin ? clock(utcAt(p.t, origin), 1) : sample ? clock(sample.timestamp, 1) : '';
  return (
    <main className="investigation" onKeyDown={onKey}>
      <section className="film" aria-label="Recording">
        <Stage c={c} p={p} sample={sample} videoRef={video} onTime={onTime} onPlay={playing => setP(q => ({...q, playing}))} onEnd={() => setP(q => ({...q, playing: false}))} />
        <div className="controls">
          {c.kind === 'video' && <button className="play" onClick={toggle} aria-label={p.playing ? 'Pause' : 'Play'}>{p.playing ? 'Pause' : 'Play'}</button>}
          <button className="step" onClick={() => step(-1)} aria-label="Previous sample">‹</button>
          <button className="step" onClick={() => step(1)} aria-label="Next sample">›</button>
          <output className="clock" aria-live="off">{readout} <small>UTC</small></output>
          {c.vision && <span className="sampled" aria-live="polite">
            {sample ? (sample.box ? (sample.near ? 'Detector sample: at the edge' : 'Detector sample: tracked') : 'Detector sample: nobody found') : 'Between detector samples'}
          </span>}
          <span className="spacer" />
          {decisive && <button className="quiet" onClick={() => seek(decisive.mediaTime)}>The climb</button>}
          {c.kind === 'video' && trigger && <button className="quiet" onClick={watch}>Play from the trigger</button>}
          {c.vision && <label className="toggle"><input type="checkbox" checked={p.box} onChange={e => setP(q => ({...q, box: e.target.checked}))} />Box</label>}
          {c.vision?.region && <label className="toggle"><input type="checkbox" checked={p.region} onChange={e => setP(q => ({...q, region: e.target.checked}))} />Region</label>}
        </div>
        <Timeline c={c} p={p} seek={seek} />
      </section>
      <Brief c={c} seek={seek} onAct={setDialog} onDetails={() => setDialog('details')} />
      {(dialog === 'request' || dialog === 'dismiss') && <Decision c={c} mode={dialog} onClose={() => setDialog(null)} onDone={onChange} />}
      {dialog === 'send' && <SendNative c={c} onClose={() => setDialog(null)} onDone={onChange} />}
      {dialog === 'details' && <Details c={c} onClose={() => setDialog(null)} />}
    </main>
  );
}

function App() {
  const [cases, setCases] = useState<Summary[]>([]);
  const [unavailable, setUnavailable] = useState<{id: string; title: string; error: string}[]>([]);
  const [assessment, setAssessment] = useState<Assessment>(null);
  const [current, setCurrent] = useState<Case | null>(null);
  const [error, setError] = useState('');
  const [newOpen, setNewOpen] = useState(false);
  const [id, setId] = useState(hashId());

  const loadIndex = useCallback(async () => {
    const r = await api('/api/casebook');
    setCases(r.cases); setUnavailable(r.unavailable); setAssessment(r.assessment ?? null);
    return r.cases as Summary[];
  }, []);
  useEffect(() => { loadIndex().then(list => { if (!hashId() && list[0]) { location.hash = `#/${list[0].id}`; } }).catch(e => setError(e.message)); }, [loadIndex]);
  useEffect(() => { const h = () => setId(hashId()); addEventListener('hashchange', h); return () => removeEventListener('hashchange', h); }, []);
  useEffect(() => {
    if (!id) return;
    setError(''); setCurrent(null);
    api(`/api/cases/${id}`).then(r => setCurrent(r.case)).catch(e => setError(e.message));
  }, [id]);
  const refreshed = (c: Case) => { setCurrent(c); void loadIndex(); };
  return (
    <>
      <header className="top">
        <span className="wordmark">Adaptive Watch</span>
        <nav aria-label="Assessments">
          {cases.map(c => (
            <a key={c.id} href={`#/${c.id}`} className={`${c.id === id ? 'on' : ''} ${c.flagship ? 'flagship' : ''}`} aria-current={c.id === id ? 'page' : undefined}>
              {c.flagship && <i className={`pip ${c.status === 'Needs review' ? 'open' : ''}`} aria-hidden="true" />}{c.title}
              {c.flagship && <small className="sr-only"> {c.status}</small>}
            </a>
          ))}
          {unavailable.map(u => <span key={u.id} className="gone" title={u.error}>{u.title} unavailable</span>)}
        </nav>
        <button className="quiet" onClick={() => setNewOpen(true)}>New assessment</button>
      </header>
      {error && <div className="problem" role="alert"><h1>This case cannot be shown</h1><p>{error}</p></div>}
      {!error && !current && <div className="loading" aria-busy="true">Loading the recording…</div>}
      {current && <Investigation key={current.id} c={current} onChange={refreshed} />}
      {newOpen && <NewAssessment a={assessment} onClose={() => setNewOpen(false)} onOpen={cid => { setNewOpen(false); void loadIndex(); location.hash = `#/${cid}`; }} />}
    </>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
