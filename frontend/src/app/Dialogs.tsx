import {useEffect, useRef, useState} from 'react';
import {api} from './api';
import type {Assessment, Case, Job} from './types';
import {clock, day} from './format';

function Modal({title, onClose, children, wide}: {title: string; onClose: () => void; children: React.ReactNode; wide?: boolean}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    const previous = document.activeElement as HTMLElement | null;
    return () => previous?.focus();
  }, []);
  return (
    <dialog ref={ref} className={wide ? 'modal wide' : 'modal'} onClose={onClose}
      onClick={e => { if (e.target === ref.current) ref.current?.close(); }} aria-labelledby="modal-title">
      <header>
        <h2 id="modal-title">{title}</h2>
        <button className="link" onClick={() => ref.current?.close()}>Close</button>
      </header>
      {children}
    </dialog>
  );
}

export function Decision({c, mode, onClose, onDone}: {c: Case; mode: 'request' | 'dismiss'; onClose: () => void; onDone: (c: Case) => void}) {
  const visible = c.flagship ? 'entry_visible' : 'condition_visible';
  const hidden = c.flagship ? 'entry_not_visible' : 'condition_not_visible';
  const [verdict, setVerdict] = useState('');
  const [note, setNote] = useState('');
  const [ack, setAck] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const path = `/api/cases/${c.id}/action`;
      const first = await api(path, {action: 'review', revision: c.actionRevision});
      const done = await api(path, {
        action: mode === 'request' ? 'save_review_request' : 'dismiss', revision: first.case.actionRevision,
        footageReviewed: true, annotation: verdict || 'not_verified', note,
      });
      onDone(done.case);
      onClose();
    } catch (err: any) {
      setError(err.status === 409 ? 'This case changed while you were reviewing. Reload to see the latest evidence.' : err.message);
    } finally {
      setBusy(false);
    }
  }
  const choices: [string, string][] = [[visible, c.flagship ? 'Entry onto the tracks' : 'The condition'], [hidden, 'Not visible'], ['uncertain', 'Cannot tell']];
  return (
    <Modal title={mode === 'request' ? 'Request XProtect review' : 'Dismiss this exception'} onClose={onClose}>
      <form onSubmit={submit}>
        {mode === 'request' && (
          <p className="lede">Creates a review exception for <b>{c.title}</b>, {day(c.interval[0])} {clock(c.interval[0])} to {clock(c.interval[1])} UTC.
            It asks a person to look. It does not say what happened.</p>
        )}
        <fieldset>
          <legend>What do you see in the footage?</legend>
          {choices.map(([v, label]) => (
            <label key={v} className="choice"><input type="radio" name="verdict" value={v} checked={verdict === v} onChange={() => setVerdict(v)} />{label}</label>
          ))}
        </fieldset>
        <label className="field">Note{verdict ? ' (required with a verdict)' : ''}
          <textarea value={note} onChange={e => setNote(e.target.value)} maxLength={2000} rows={3} />
        </label>
        <label className="choice"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />I watched the relevant footage</label>
        {error && <p role="alert" className="error">{error}</p>}
        <div className="row">
          <button className="primary" disabled={!ack || busy || (!!verdict && !note.trim())}>{mode === 'request' ? 'Save review request' : 'Dismiss'}</button>
          <button type="button" className="quiet" onClick={onClose}>Cancel</button>
        </div>
        <p className="fine">Saved on this computer for this case only. A saved request is not an XProtect alarm.</p>
      </form>
    </Modal>
  );
}

export function Details({c, onClose}: {c: Case; onClose: () => void}) {
  const h = c.hafnia;
  const limits = [...c.limitations, ...(c.agent ? [c.agent.limits] : []), 'Evidence comes from controlled synthetic camera scenarios, not from deployment.'];
  return (
    <Modal title="Evidence details" onClose={onClose} wide>
      <div className="details">
        <section>
          <h3>Hafnia</h3>
          {h.answers
            ? h.answers.map(a => <div key={a.summaryId}><p className="mono">{a.summaryId}</p><p className="quiet-text">{a.prompt}</p><pre>{a.quote}</pre></div>)
            : <><p className="mono">{h.summaryId}</p><p className="quiet-text">{h.request}</p><pre>{h.quote}</pre></>}
        </section>
        {c.vision && (
          <section>
            <h3>Local vision</h3>
            <p>{c.vision.label}. {c.vision.model}</p>
            {c.vision.regionStatus && <p>Region: {c.vision.regionStatus}.</p>}
            <p>{c.vision.meaning}</p>
          </section>
        )}
        {c.agent && (
          <section>
            <h3>Reviewed footage</h3>
            <p><b>{c.agent.reviewer}</b>. {c.agent.provenance}</p>
            <p>{c.agent.basis}</p>
            <ul>{c.agent.observations.map(o => <li key={o.timestamp}><span className="mono">{clock(o.timestamp, 1)}</span> {o.what}</li>)}</ul>
          </section>
        )}
        <section>
          <h3>Limits</h3>
          <ul>{limits.map(l => <li key={l}>{l}</li>)}</ul>
        </section>
        <section>
          <h3>Source</h3>
          <p className="mono">{c.camera} · {c.interval.join(' to ')}</p>
          {c.video && <p className="mono">Video sha256 {c.video.sha256}</p>}
          {c.diagnostic && <p>{c.diagnostic.note}</p>}
        </section>
      </div>
    </Modal>
  );
}

const ICON: Record<string, string> = {waiting: '○', running: '◐', done: '●', failed: '✕', needs_you: '◆'};

export function NewAssessment({a, onClose, onOpen}: {a: Assessment; onClose: () => void; onOpen: (id: string) => void}) {
  const [camera, setCamera] = useState(a?.cameras[0]?.id ?? '');
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!job || ['completed', 'failed'].includes(job.state)) return;
    const timer = setInterval(async () => {
      try { setJob((await api(`/api/jobs/${job.id}`)).job); } catch (e: any) { setError(e.message); }
    }, 1500);
    return () => clearInterval(timer);
  }, [job]);
  async function start() {
    setError('');
    try { setJob((await api('/api/jobs', {cameraId: camera})).job); } catch (e: any) { setError(e.message); }
  }
  async function confirm() {
    if (!job) return;
    try { setJob((await api('/api/jobs/continuity', {id: job.id, reviewed: true})).job); } catch (e: any) { setError(e.message); }
  }
  return (
    <Modal title="New assessment" onClose={onClose}>
      {!a?.available && <><p className="lede">{a?.reason ?? 'New assessments are unavailable.'}</p>{a?.next && <p className="quiet-text">{a.next}</p>}</>}
      {a?.available && !job && (
        <div>
          <p className="lede">Records the last 15 seconds of the camera, asks Hafnia about it once, runs local vision on the GPU, and compares the two. Uses one Hafnia request.</p>
          <label className="field">Camera
            <select value={camera} onChange={e => setCamera(e.target.value)}>{a.cameras.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select>
          </label>
          <div className="row"><button className="primary" onClick={start}>Start assessment</button></div>
        </div>
      )}
      {job && (
        <div>
          <ol className="stages">
            {job.stages.map(s => (
              <li key={s.key} className={s.status}><span aria-hidden="true">{ICON[s.status]}</span><div><strong>{s.label}</strong>{s.detail && <small>{s.detail}</small>}</div></li>
            ))}
          </ol>
          {job.state === 'awaiting_continuity' && (
            <div className="callout">
              {job.video && <video className="continuity" src={job.video} controls muted playsInline />}
              <p>Watch the recording. The camera replays a short clip on a loop, so check there is no restart or jump partway through. No restart was detected automatically.</p>
              <button className="primary" onClick={confirm}>Continuous. Go on</button></div>
          )}
          {job.error && <p role="alert" className="error"><b>{job.error.reason}</b> {job.error.next}</p>}
          {job.state === 'completed' && job.caseId && <div className="row"><button className="primary" onClick={() => onOpen(job.caseId!)}>Open result</button></div>}
        </div>
      )}
      {error && <p role="alert" className="error">{error}</p>}
    </Modal>
  );
}

export function SendNative({c, onClose, onDone}: {c: Case; onClose: () => void; onDone: (c: Case) => void}) {
  const [preview, setPreview] = useState<null | {sha256: string; destination: string; camera: string; event: string; consequence: string; enabled: boolean; previous: {state: string}[]}>(null);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api(`/api/cases/${c.id}/native`, {action: 'preview'}).then(r => setPreview(r.preview)).catch(e => setError(e.message)); }, [c.id]);
  async function send() {
    if (!preview) return;
    setBusy(true); setError('');
    try {
      const r = await api(`/api/cases/${c.id}/native`, {action: 'send', approval: preview.sha256.slice(0, 16), confirmed: true});
      onDone(r.case); onClose();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Send to XProtect" onClose={onClose}>
      <div>
        {!preview && !error && <p className="lede">Preparing the event…</p>}
        {preview && (
          <>
            <dl className="facts">
              <div><dt>Event</dt><dd>{preview.event}</dd></div>
              <div><dt>Camera</dt><dd>{preview.camera}</dd></div>
              <div><dt>Destination</dt><dd className="mono">XProtect Event Server {preview.destination}</dd></div>
              <div><dt>Fingerprint</dt><dd className="mono">{preview.sha256.slice(0, 16)}</dd></div>
            </dl>
            <p className="lede">{preview.consequence}</p>
            {preview.previous.length > 0 && <p className="error">This event was already attempted ({preview.previous[preview.previous.length - 1].state}). It will not be sent again automatically.</p>}
            {!preview.enabled && <p className="quiet-text">Sending is switched off for this session.</p>}
            <label className="choice"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />Send this one event to XProtect</label>
          </>
        )}
        {error && <p role="alert" className="error">{error}</p>}
        <div className="row"><button className="primary" disabled={!preview || !preview.enabled || !ack || busy || preview.previous.length > 0} onClick={send}>Send event</button>
          <button className="quiet" onClick={onClose}>Cancel</button></div>
      </div>
    </Modal>
  );
}
