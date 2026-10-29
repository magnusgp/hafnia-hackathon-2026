import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError } from './api';
import { clock, cameraLabel, hms, stamp, VERDICT_LABEL } from './format';
import type { Investigation as Inv, NativePreview, Sample } from './types';
import { Chip, Dialog, Notice, Source, Spinner } from './ui';

const ROOT = (i: Inv) => (i.kind === 'archive' ? `/api/archive/${i.id}` : `/api/exceptions/${i.id}`);

/** The sample the footage is showing right now: the latest one at or before the playhead, within one sample interval. */
export function sampleAt(samples: Sample[], t: number): Sample | null {
  let best: Sample | null = null;
  for (const s of samples) if (s.mediaTime !== null && s.mediaTime <= t + 0.05) best = s;
  return best && t - (best.mediaTime as number) <= 0.6 ? best : null;
}

export function Investigation({ id, origin, onChanged }: { id: string; origin: 'live' | 'archive'; onChanged: () => void }) {
  const [inv, setInv] = useState<Inv | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try { setInv(await api.get<Inv>(origin === 'archive' ? `/api/archive/${id}` : `/api/exceptions/${id}`)); }
    catch (e) { setInv(null); setError(e instanceof ApiError ? e.message : 'Could not load this record.'); }
  }, [id, origin]);
  useEffect(() => { setInv(null); void load(); }, [load]);
  if (error) return <div className="invest"><Notice tone="bad" title="This record cannot be shown" action={<button className="quiet" onClick={load}>Try again</button>}>{error}</Notice></div>;
  if (!inv) return <div className="invest"><Spinner label="Loading the recording and its evidence…" /></div>;
  return <Loaded key={inv.id} inv={inv} reload={async () => { await load(); onChanged(); }} />;
}

function Loaded({ inv, reload }: { inv: Inv; reload: () => Promise<void> }) {
  const video = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(inv.video?.duration ?? 0);
  const [ratio, setRatio] = useState(16 / 9);
  const [showBox, setShowBox] = useState(true);
  const [showRegion, setShowRegion] = useState(true);
  const [details, setDetails] = useState(false);
  const samples = inv.vision?.samples ?? [];
  const trigger = inv.vision?.trigger ?? null;
  const current = useMemo(() => sampleAt(samples, t), [samples, t]);
  const seek = useCallback((time: number) => {
    const v = video.current;
    if (!v) return;
    v.pause();
    v.currentTime = Math.min(Math.max(0, time), duration || v.duration || 0);
    setT(v.currentTime);
  }, [duration]);

  useEffect(() => { if (trigger?.mediaTime != null) seek(trigger.mediaTime); }, [trigger?.mediaTime, seek, inv.id]);
  useEffect(() => {
    let raf = 0;
    const tick = () => { if (video.current) setT(video.current.currentTime); raf = requestAnimationFrame(tick); };
    if (playing) raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const timed = samples.filter((s) => s.mediaTime !== null);
  const step = (dir: 1 | -1) => {
    const next = dir > 0 ? timed.find((s) => (s.mediaTime as number) > t + 0.05) : [...timed].reverse().find((s) => (s.mediaTime as number) < t - 0.05);
    if (next) seek(next.mediaTime as number);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest('input,textarea,select')) return;
    if (e.key === ' ') { e.preventDefault(); playing ? video.current?.pause() : void video.current?.play(); }
    if (e.key === 'ArrowRight') { e.preventDefault(); step(1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
  };
  const box = showBox && current?.box ? current.box : null;
  const cond = inv.review?.condition ?? inv.title ?? 'The recorded event';

  return (
    <div className="invest-wrap">
    <section className="invest" onKeyDown={onKey} aria-label="Investigation">
      <header className="inv-head">
        <div>
          <h1>{cond}</h1>
          <p className="meta">
            <span>{cameraLabel(inv.camera.name)}</span><span className="sep">·</span>
            <span className="mono">{stamp(inv.at)}</span>
            {inv.watch ? <><span className="sep">·</span><span>Watch “{inv.watch.name}” v{inv.watch.version}</span></> : <Chip tone="plain" title={inv.note}>Recorded before Watches</Chip>}
          </p>
        </div>
        <button className="quiet small" onClick={() => setDetails(true)}>Evidence details</button>
      </header>

      {inv.video ? (
        <>
          <div className="stage" style={{ aspectRatio: String(ratio), ['--ratio' as string]: ratio }}>
            <video ref={video} src={inv.video.url} preload="auto" muted playsInline
              onLoadedMetadata={(e) => { setDuration(e.currentTarget.duration); setRatio(e.currentTarget.videoWidth / e.currentTarget.videoHeight || 16 / 9); if (trigger?.mediaTime != null) seek(trigger.mediaTime); }}
              onPlay={() => setPlaying(true)} onPause={() => { setPlaying(false); if (video.current) setT(video.current.currentTime); }}
              onEnded={() => setPlaying(false)} onSeeked={() => video.current && setT(video.current.currentTime)} />
            <svg className="overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
              {showRegion && inv.vision?.region && <polygon className="region" points={inv.vision.region.polygon.map((p) => p.join(',')).join(' ')} />}
              {box && <rect className="detbox" x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} />}
            </svg>
            {box && <span className="boxtag mono" style={{ left: `${box[0] * 100}%`, top: `${box[1] * 100}%` }}>person{current?.near ? ' · at the region' : ''}</span>}
          </div>
          <div className="controls">
            <button className="quiet" onClick={() => (playing ? video.current?.pause() : void video.current?.play())} aria-label={playing ? 'Pause' : 'Play'}>{playing ? 'Pause' : 'Play'}</button>
            <button className="quiet" onClick={() => step(-1)} aria-label="Previous detector sample" disabled={!timed.length}>‹</button>
            <button className="quiet" onClick={() => step(1)} aria-label="Next detector sample" disabled={!timed.length}>›</button>
            {trigger?.mediaTime != null && <button className="quiet" onClick={() => seek(trigger.mediaTime as number)}>Go to trigger</button>}
            <span className="mono clock">{clock(t)} / {clock(duration)}</span>
            <span className="grow" />
            {inv.vision?.region && <label className="check"><input type="checkbox" checked={showRegion} onChange={(e) => setShowRegion(e.target.checked)} />Region</label>}
            <label className="check"><input type="checkbox" checked={showBox} onChange={(e) => setShowBox(e.target.checked)} />Detection</label>
          </div>
          <Timeline inv={inv} t={t} duration={duration} seek={seek} />
        </>
      ) : <Notice>No original video is saved for this record.</Notice>}

      {inv.kind === 'live' ? <DecisionBar inv={inv} reload={reload} /> : <ArchiveStatus inv={inv} />}
      {details && <Details inv={inv} onClose={() => setDetails(false)} />}
    </section>
    <Sources inv={inv} current={current} seek={seek} />
    </div>
  );
}

function Sources({ inv, current, seek }: { inv: Inv; current: Sample | null; seek: (t: number) => void }) {
  const v = inv.vision;
  const trig = v?.trigger;
  return (
    <aside className="sources" aria-label="What each source established">
      <div className="reason"><span className="label">Why it was raised</span><p><b>{inv.policy.label}.</b> {inv.reason}</p></div>
      <article className="src hafnia">
        <header><Source who="hafnia" /><Chip tone="plain" title="Hafnia is a model reading the footage. This is not a human review.">AI footage review</Chip></header>
        <p className={`answer-line ${inv.hafnia.tone ?? ''}`}>{inv.hafnia.answer ?? 'No answer saved'}</p>
        {inv.hafnia.quote && <blockquote>“{inv.hafnia.quote}”</blockquote>}
        {inv.hafnia.timing && inv.hafnia.timing !== 'unknown' && <p className="small">Timing it gave: {inv.hafnia.timing}</p>}
      </article>
      <article className="src vision">
        <header><Source who="vision" />{v?.detector && <Chip tone="plain">{v.detector === 'person_region_proximity' ? 'Person near region' : v.detector}</Chip>}</header>
        {v && trig ? (<>
          <p className="answer-line">Person at the region from <span className="mono">{hms(trig.timestamp)}</span></p>
          <p className="small">{v.meaning}</p>
          <button className="link" onClick={() => trig.mediaTime != null && seek(trig.mediaTime)}>Show that moment</button>
          {current?.box && <p className="small now">Playing now: {current.near ? 'person at the region' : 'person elsewhere in the frame'}</p>}
        </>) : <p className="small">{v ? 'No detected person reached the region.' : 'No local vision output is saved for this record.'}</p>}
        {v?.device && <p className="small mono">{v.device}</p>}
      </article>
      <p className="hint">The two sources are kept apart. Neither is treated as the other’s answer.</p>
    </aside>
  );
}

function Timeline({ inv, t, duration, seek }: { inv: Inv; t: number; duration: number; seek: (t: number) => void }) {
  const samples = (inv.vision?.samples ?? []).filter((s) => s.mediaTime !== null);
  const trig = inv.vision?.trigger;
  const pct = (x: number) => `${Math.min(100, Math.max(0, (x / (duration || 1)) * 100))}%`;
  const click = (e: React.MouseEvent<HTMLDivElement>) => { const r = e.currentTarget.getBoundingClientRect(); seek(((e.clientX - r.left) / r.width) * duration); };
  return (
    <div className="timeline" aria-label="Synchronized timeline">
      <div className="lane"><Source who="hafnia" />
        <div className="track" onClick={click}><div className={`answer ${inv.hafnia.tone ?? ''}`} style={{ left: 0, right: 0 }}>{inv.hafnia.answer ?? 'No answer'} <small>(one answer for the whole recording)</small></div><i className="head" style={{ left: pct(t) }} /></div>
      </div>
      <div className="lane"><Source who="vision" />
        <div className="track" onClick={click}>
          {samples.map((s) => <b key={s.index} className={`dot${s.near ? ' near' : ''}${s.box ? '' : ' none'}`} style={{ left: pct(s.mediaTime as number) }} title={`${hms(s.timestamp)} UTC${s.near ? ' · person at the region' : ''}`} />)}
          {trig?.mediaTime != null && <em className="mark-trig" style={{ left: pct(trig.mediaTime) }} title={`First at the region ${hms(trig.timestamp)} UTC`} />}
          <i className="head" style={{ left: pct(t) }} />
        </div>
      </div>
    </div>
  );
}

function ArchiveStatus({ inv }: { inv: Inv }) {
  const d = inv.decision;
  return (
    <div className="decision-bar readonly">
      <div className="statline"><b>Decision on file</b>
        <span>{d.status === 'review_requested' ? `Review requested: ${VERDICT_LABEL[d.verdict ?? ''] ?? '—'}` : d.status}{d.note ? ` · “${d.note}”` : ''}</span>
        {d.at && <span className="mono">{stamp(d.at)}</span>}
      </div>
      <NativeLine inv={inv} />
      <p className="hint">This is a verified record from before Watches existed. It is shown as saved and cannot be changed here.</p>
    </div>
  );
}

export function NativeLine({ inv }: { inv: Inv }) {
  const n = inv.native;
  const transport = n.transport?.state === 'accepted' || n.state === 'sent';
  return (
    <ol className="steps" aria-label="XProtect handoff">
      <li className={inv.decision.status === 'review_requested' ? 'done' : ''}><b>Review decision</b><span>{inv.decision.status === 'review_requested' ? 'Requested' : inv.decision.status === 'undecided' ? 'Not decided yet' : 'No alert requested'}</span></li>
      <li className={transport ? 'done' : n.state === 'blocked' || n.state === 'uncertain' ? 'bad' : ''}><b>Event Server</b>
        <span>{transport ? `Accepted${n.transport?.at ? ' · ' + stamp(n.transport.at) : ''}` : n.state === 'uncertain' ? 'Result uncertain, not resent' : n.state === 'blocked' ? 'Not accepted' : n.state === 'not_configured' ? 'No alarm set up' : 'Nothing sent'}</span></li>
      <li className={n.smartClient === 'verified' ? 'done' : ''}><b>Smart Client</b><span>{n.smartClient === 'verified' ? `Alarm verified${n.alarm ? ' · ' + n.alarm : ''}` : 'Not verified yet'}</span></li>
    </ol>
  );
}

function DecisionBar({ inv, reload }: { inv: Inv; reload: () => Promise<void> }) {
  const review = inv.review!;
  const d = inv.decision;
  const [verdict, setVerdict] = useState<string>('');
  const [note, setNote] = useState('');
  const [watched, setWatched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<NativePreview | null>(null);
  const decided = d.status !== 'undecided';

  const save = async (outcome: string) => {
    setBusy(true); setError(null);
    try {
      await api.post(`${ROOT(inv)}/decision`, { expectedRevision: d.revision, verdict, note, watchedFootage: watched, outcome });
      await reload();
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The decision was not saved.');
      if (e instanceof ApiError && e.code === 'stale_revision') await reload();
      return false;
    } finally { setBusy(false); }
  };
  const openPreview = async () => {
    setBusy(true); setError(null);
    try { setPreview((await api.post<{ preview: NativePreview }>(`${ROOT(inv)}/native`, { action: 'preview' })).preview); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'The event could not be prepared.'); }
    finally { setBusy(false); }
  };
  const sendOutcome = review.outcomes.find((o) => o.id === 'escalate');
  const ready = verdict !== '' && watched && (verdict === 'unclear' || note.trim() !== '');

  if (decided) {
    return (
      <div className="decision-bar done">
        <div className="statline"><b>Your decision</b>
          <span>{review.condition}: {VERDICT_LABEL[d.verdict ?? ''] ?? '—'}{d.note ? ` · “${d.note}”` : ''}</span>
          <Chip tone={d.status === 'review_requested' ? 'good' : 'plain'}>{d.status === 'review_requested' ? 'Review requested' : d.status === 'dismissed' ? 'Dismissed' : 'Confirmed, no alert'}</Chip>
        </div>
        <NativeLine inv={inv} />
        {d.status === 'review_requested' && inv.native.state === 'ready' && <div className="row"><button className="primary" onClick={openPreview} disabled={busy}>Review and send to XProtect…</button><span className="hint">Nothing has been sent yet.</span></div>}
        {inv.native.state === 'sent' && <p className="hint">{inv.native.detail}</p>}
        {(inv.native.state === 'uncertain' || inv.native.state === 'blocked') && <Notice tone="review" title="This event will not be sent again">{inv.native.detail}</Notice>}
        {error && <Notice tone="bad">{error}</Notice>}
        {preview && <SendDialog inv={inv} preview={preview} onClose={() => setPreview(null)} onDone={async () => { setPreview(null); await reload(); }} />}
      </div>
    );
  }
  return (
    <form className="decision-bar" onSubmit={(e) => e.preventDefault()} aria-label="Review decision">
      <div className="q"><b>{review.question}</b><span className="tag">Human review · yours</span></div>
      <div className="answer-row">
        <div className="seg" role="radiogroup" aria-label={review.question}>
          {review.options.map((o) => (
            <label key={o.id} className={verdict === o.id ? 'on' : ''}><input type="radio" name="verdict" value={o.id} checked={verdict === o.id} onChange={() => setVerdict(o.id)} />{o.label}</label>
          ))}
        </div>
        <input className="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={verdict === 'unclear' ? 'Note (optional)' : 'What does the footage show? A short note'} maxLength={300} aria-label="Note" disabled={!verdict} />
      </div>
      <div className="row">
        <label className="check"><input type="checkbox" checked={watched} onChange={(e) => setWatched(e.target.checked)} />I watched the relevant footage</label>
        <span className="grow" />
        <button className="quiet" disabled={!ready || busy} onClick={() => save('dismiss')}>Dismiss</button>
        <button className="quiet" disabled={!ready || busy} onClick={() => save('confirm_local')}>Confirm, no alert</button>
        <button className="primary" disabled={!ready || busy || sendOutcome?.enabled === false} title={sendOutcome?.why ?? undefined}
          onClick={async () => { if (await save('escalate')) await openPreview(); }}>Send to XProtect…</button>
      </div>
      {sendOutcome?.enabled === false && <p className="hint warn">{sendOutcome.why}</p>}
      {error && <Notice tone="bad">{error}</Notice>}
      {preview && <SendDialog inv={inv} preview={preview} onClose={() => setPreview(null)} onDone={async () => { setPreview(null); await reload(); }} />}
    </form>
  );
}

function SendDialog({ inv, preview, onClose, onDone }: { inv: Inv; preview: NativePreview; onClose: () => void; onDone: () => Promise<void> }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const already = preview.previous.length > 0;
  const send = async () => {
    setBusy(true); setError(null);
    try { await api.post(`/api/exceptions/${inv.id}/native`, { action: 'send', confirmed: true, approval: preview.sha256.slice(0, 16) }); await onDone(); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'The event was not sent.'); setBusy(false); }
  };
  return (
    <Dialog title="Send this review event to XProtect" onClose={onClose} wide>
      <dl className="facts">
        <dt>Camera</dt><dd>{cameraLabel(preview.camera)}</dd>
        <dt>Source time</dt><dd className="mono">{stamp(inv.at)}</dd>
        <dt>Event</dt><dd>{preview.event}</dd>
        <dt>Alarm</dt><dd>{preview.alarm}</dd>
        <dt>Destination</dt><dd className="mono">Event Server {preview.destination}</dd>
        <dt>Message</dt><dd>{inv.handoff?.message}</dd>
        <dt>Fingerprint</dt><dd className="mono">{preview.sha256.slice(0, 16)}…</dd>
      </dl>
      <p className="hint">{preview.consequence} Each event is sent once and recorded in the duplicate-send ledger.</p>
      <details><summary>Exact event (XML)</summary><pre className="xml">{preview.xml}</pre></details>
      {!preview.enabled && <Notice tone="review" title="Sending is switched off in this session">The event can be inspected but not sent. Start Ortru with sending enabled to send.</Notice>}
      {already && <Notice tone="review" title="Already handled">This exact event has {preview.previous.length} earlier attempt{preview.previous.length > 1 ? 's' : ''} in the ledger: {preview.previous.map((p) => p.state).join(', ')}. It will not be sent again.</Notice>}
      {error && <Notice tone="bad">{error}</Notice>}
      <label className="check big"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />I confirm sending this event to XProtect now</label>
      <div className="row end"><button className="quiet" onClick={onClose}>Not now</button><button className="primary" disabled={!confirm || busy || !preview.enabled || already} onClick={send}>Send event</button></div>
    </Dialog>
  );
}

function Details({ inv, onClose }: { inv: Inv; onClose: () => void }) {
  const cfg = inv.provenance.watchConfig;
  return (
    <Dialog title="Evidence details" onClose={onClose} wide>
      <div className="details">
        <section><h3>Hafnia (AI footage review)</h3>
          {inv.hafnia.prompt && <><p className="label">Exact request</p><p className="quote">{inv.hafnia.prompt}</p></>}
          {inv.hafnia.quote && <><p className="label">Original wording</p><p className="quote">{inv.hafnia.quote}</p></>}
          {inv.hafnia.limitations && <><p className="label">Hafnia’s stated limits</p><p>{inv.hafnia.limitations}</p></>}
          {inv.hafnia.summaryId && <p className="mono">Summary {inv.hafnia.summaryId}</p>}
        </section>
        {inv.vision && <section><h3>Local vision</h3>
          <p>{inv.vision.device ?? 'Detector'}{inv.vision.model ? ` · ${inv.vision.model}` : ''}</p>
          {inv.vision.meaning && <p>{inv.vision.meaning}</p>}
          <p className="mono">{inv.vision.samples.length} samples{inv.vision.samplesPerSecond ? ` at ${inv.vision.samplesPerSecond}/s` : ''}{inv.vision.parameters ? ` · ${JSON.stringify(inv.vision.parameters)}` : ''}</p>
        </section>}
        {cfg && <section><h3>Watch configuration used (version {inv.watch?.version})</h3>
          <p className="mono">camera {cfg.camera.id}</p><p className="mono">detector {cfg.detector.id}</p><p className="mono">cadence every {cfg.schedule.intervalMinutes} min · window {cfg.schedule.windowSeconds} s</p>
          <p className="mono">raises on {cfg.policy.raiseOn.join(', ')}</p></section>}
        <section><h3>Source files</h3>
          <ul className="hashes">{inv.provenance.hashes.map((h) => <li key={h.path ?? h.name}><span>{h.name}</span><code>{h.sha256.slice(0, 20)}…</code></li>)}</ul>
          {inv.provenance.continuity && <p className="hint">Continuity: {inv.provenance.continuity}</p>}
        </section>
        <section><h3>Limits</h3><ul>{(inv.limitations ?? []).map((l) => <li key={l}>{l}</li>)}</ul>{inv.provenance.human && <p className="hint">{inv.provenance.human}</p>}</section>
      </div>
    </Dialog>
  );
}
