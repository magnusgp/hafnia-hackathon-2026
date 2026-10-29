import { useState } from 'react';
import { api, ApiError } from './api';
import { ago, cameraLabel, stamp, until } from './format';
import { RegionDrawer } from './RegionDrawer';
import type { Bootstrap, Job, Watch } from './types';
import { Chip, Empty, Notice, Source } from './ui';

const STATUS: Record<string, { label: string; tone: 'plain' | 'good' | 'review' | 'bad' }> = {
  draft: { label: 'Draft', tone: 'plain' }, active: { label: 'Active', tone: 'good' }, paused: { label: 'Paused', tone: 'review' }, disabled: { label: 'Disabled', tone: 'plain' },
};

export function WatchList({ boot, open, create }: { boot: Bootstrap; open: (id: string) => void; create: () => void }) {
  return (
    <div className="page">
      <header className="page-head"><div><h1>Watches</h1><p className="sub">Each Watch guards one camera with its own question for Hafnia, its own local vision check and its own policy.</p></div>
        <button className="primary" onClick={create}>Create Watch</button></header>
      {!boot.gateway.available && <Notice tone="review" title="Hafnia gateway: sign-in needed">{boot.gateway.reason}</Notice>}
      {boot.watches.length === 0
        ? <Empty title="No Watches yet" action={<button className="primary" onClick={create}>Create the first Watch</button>}>Pick a camera, write what Hafnia should look for, outline a region on the picture and set how often to look.</Empty>
        : <ul className="cards watches">{boot.watches.map((w) => {
          const s = STATUS[w.status];
          return (<li key={w.id}><button className="card" onClick={() => open(w.id)}>
            <span className="card-top"><b>{w.config.name}</b><Chip tone={s.tone}>{s.label}</Chip></span>
            <span>{cameraLabel(w.config.camera.name)}</span>
            <span className="quote">“{w.config.hafnia.instruction}”</span>
            <span className="hint">{w.status === 'active' ? `Next look ${until(w.schedule.nextDue)}` : w.status === 'draft' ? 'Not running yet' : 'Not running'} · {w.schedule.usedToday} of {w.schedule.budgetPerDay} requests today</span>
          </button></li>);
        })}</ul>}
    </div>
  );
}

function JobRow({ job, retry, openException }: { job: Job; retry: (id: string) => void; openException: (id: string) => void }) {
  const failed = job.state === 'failed';
  const waiting = job.stages.find((s) => s.status === 'needs_you');
  return (
    <li className={`job ${failed ? 'failed' : job.state === 'completed' ? 'done' : ''}`}>
      <div className="job-top"><span className="mono">{stamp(job.interval[0])}</span><span className="hint">{job.trigger === 'manual' ? 'Run by you' : 'Scheduled'} · {ago(job.created)}</span>
        <span className="grow" />{job.state === 'completed' && <button className="link" onClick={() => openException(job.id)}>Open result</button>}
        {failed && !job.resumable && <button className="link" onClick={() => retry(job.id)}>Retry</button>}</div>
      <ol className="stages">{job.stages.map((s) => <li key={s.key} className={s.status} title={s.detail}><i aria-hidden="true" />{s.label}</li>)}</ol>
      {failed && job.error && <p className="jerr"><b>{job.error.reason}.</b> {job.error.next}</p>}
      {waiting && !failed && <p className="jerr wait">{waiting.detail}</p>}
      {job.state === 'completed' && job.stages[3]?.detail && <p className="hint">{job.stages[3].detail}</p>}
    </li>
  );
}

export function WatchPage({ boot, watch, edit, back, refresh, openException }: {
  boot: Bootstrap; watch: Watch; edit: () => void; back: () => void; refresh: () => Promise<void>; openException: (id: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const c = watch.config;
  const s = STATUS[watch.status];
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); await refresh(); } catch (e) { setError(e instanceof ApiError ? e.message : 'That did not work.'); await refresh(); } finally { setBusy(false); }
  };
  const setStatus = (status: string) => act(() => api.post(`/api/watches/${watch.id}/status`, { status, baseVersion: watch.version }));
  const run = () => act(() => api.post(`/api/watches/${watch.id}/run`, {}));
  const retry = (id: string) => act(() => api.post(`/api/jobs/${id}/retry`, {}));
  const cap = boot.capabilities.find((x) => x.id === c.detector.id);
  const sc = watch.schedule;
  const snap = `/api/watches/${watch.id}/snapshot`;
  return (
    <div className="page watch-page">
      <button className="link back" onClick={back}>‹ All Watches</button>
      <header className="page-head"><div><h1>{c.name}</h1>
        <p className="meta"><span>{cameraLabel(c.camera.name)}</span><span className="sep">·</span><Chip tone={s.tone}>{s.label}</Chip><span className="sep">·</span><span className="mono">version {watch.version}</span></p></div>
        <div className="actions">
          <button className="quiet" onClick={edit}>Edit</button>
          {watch.status === 'active' ? <button className="quiet" disabled={busy} onClick={() => setStatus('paused')}>Pause</button> : watch.status !== 'disabled' && <button className="primary" disabled={busy} onClick={() => setStatus('active')}>{watch.status === 'paused' ? 'Resume' : 'Activate'}</button>}
          {watch.status === 'disabled' && <button className="quiet" disabled={busy} onClick={() => setStatus('active')}>Re-activate</button>}
          {watch.status !== 'disabled' && <button className="quiet" disabled={busy} onClick={() => setStatus('disabled')}>Disable</button>}
          <button className="quiet" disabled={busy || watch.status === 'disabled' || !!sc.runningJob} onClick={run}>Assess the latest window now</button>
        </div></header>
      {error && <Notice tone="bad" title="Not done">{error}</Notice>}
      {!boot.gateway.available && watch.status !== 'disabled' && <Notice tone="review" title="Hafnia gateway: sign-in needed">Recorded windows are read and local vision runs, then the assessment waits for the Hafnia step. Nothing is sent to Hafnia until the gateway password is entered in the Ortru server window.</Notice>}
      <div className="watch-grid">
        <div className="col">
        <section className="panel"><h2><Source who="hafnia" /></h2>
          <p className="label">Question</p><p className="quote">“{c.hafnia.instruction}”</p>
          <p className="label">Visible condition</p><p>{c.hafnia.condition}</p>
          <details className="adv"><summary>Exact request and answer format</summary><p className="quote">{c.hafnia.prompt}</p></details></section>
        <section className="panel"><h2>Schedule and budget</h2>
          <dl className="facts">
            <dt>Cadence</dt><dd>Every {c.schedule.intervalMinutes} min, {c.schedule.windowSeconds} s of recording</dd>
            <dt>Next evaluation</dt><dd>{watch.status === 'active' ? until(sc.nextDue) : 'not scheduled'}</dd>
            <dt>Last completed</dt><dd>{sc.lastAssessment ? `${ago(sc.lastAssessment.at)}` : 'none yet'}</dd>
            <dt>Hafnia today</dt><dd>{sc.usedToday} of {sc.budgetPerDay} for this Watch · {sc.globalUsedToday} of {sc.globalBudget} overall</dd>
          </dl>
          {sc.lastCheck && <p className="hint">Last check: {sc.lastCheck.text}</p>}
          <p className="hint">Raises on: {c.policy.raiseOn.join(', ').replace(/_/g, ' ')}.</p></section>
        </div>
        <div className="col">
        <section className="panel"><h2><Source who="vision" /></h2>
          <p className="label">Capability</p><p>{cap?.label ?? c.detector.id}</p>
          <div className="mini"><RegionDrawer src={snap} region={c.region} readOnly /></div>
          <details className="adv"><summary>Detector settings</summary><p className="mono">{JSON.stringify(c.detector.parameters)}</p><p className="mono">camera {c.camera.id}</p><p className="hint">{cap?.cannot}</p></details></section>
        <section className="panel"><h2>XProtect</h2>
          {c.native.alarm ? <><p>Event “{c.native.event}” → alarm “{c.native.alarm}”.</p><p className="hint">Exceptions from this Watch can be sent after a saved review and your explicit confirmation.</p></>
            : <Notice tone="review" title="Review only: no alarm is set up">{watch.problems[0]?.text}</Notice>}</section>
        </div>
      </div>
      <section className="panel wide"><h2>Assessments</h2>
        {watch.jobs.length === 0 ? <p className="hint">No recorded window has been assessed yet. {watch.status === 'active' ? 'The first look is due now.' : 'Activate the Watch or assess the latest window now.'}</p>
          : <ul className="jobs">{watch.jobs.map((j) => <JobRow key={j.id} job={j} retry={retry} openException={openException} />)}</ul>}
      </section>
      <details className="panel wide"><summary>History</summary>
        <ul className="history">{[...watch.history].reverse().map((h, i) => <li key={i}><span className="mono">{stamp(h.at)}</span> {h.text}</li>)}</ul></details>
    </div>
  );
}
