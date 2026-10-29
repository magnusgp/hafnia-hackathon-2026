import { useMemo, useState } from 'react';
import { api, ApiError } from './api';
import { cameraLabel } from './format';
import { RegionDrawer } from './RegionDrawer';
import type { Bootstrap, Region, Watch, WatchConfig } from './types';
import { Chip, Notice, Spinner } from './ui';

type Form = {
  name: string; cameraId: string; instruction: string; condition: string; detectorId: string; margin: number; region: Region | null;
  raiseOn: string[]; intervalMinutes: number; windowSeconds: number; perDay: number;
};

const DEFAULT_RAISE = ['disagreement', 'corroborated', 'unresolved'];
const RAISE_HELP: Record<string, string> = {
  disagreement: 'Hafnia saw no match, but local vision found a person at the region',
  corroborated: 'Hafnia reports it and local vision agrees',
  unresolved: 'Hafnia could not decide (unsure or unusable answer) and local vision found a person',
  hafnia_only: 'Hafnia reports it but local vision saw nothing near the region',
};
const CADENCE = [[5, 'Every 5 minutes'], [15, 'Every 15 minutes'], [30, 'Every 30 minutes'], [60, 'Hourly'], [240, 'Every 4 hours'], [1440, 'Daily']] as const;

function fromWatch(w: Watch): Form {
  const c = w.config;
  return { name: c.name, cameraId: c.camera.id, instruction: c.hafnia.instruction, condition: c.hafnia.condition, detectorId: c.detector.id, margin: c.detector.parameters.margin ?? 0,
    region: c.region, raiseOn: c.policy.raiseOn, intervalMinutes: c.schedule.intervalMinutes, windowSeconds: c.schedule.windowSeconds, perDay: c.quota.perDay };
}
const blank = (cameraId: string): Form => ({ name: '', cameraId, instruction: '', condition: '', detectorId: 'person_region_proximity', margin: 0, region: null,
  raiseOn: DEFAULT_RAISE, intervalMinutes: 15, windowSeconds: 15, perDay: 20 });
function payload(f: Form) {
  return { name: f.name, cameraId: f.cameraId, hafnia: { instruction: f.instruction, condition: f.condition }, detector: { id: f.detectorId, parameters: { margin: f.margin } },
    region: f.region, schedule: { intervalMinutes: f.intervalMinutes, windowSeconds: f.windowSeconds }, quota: { perDay: f.perDay }, policy: { raiseOn: f.raiseOn } };
}

export function WatchEditor({ boot, watch, done, cancel, refresh }: { boot: Bootstrap; watch: Watch | null; done: (id: string) => void; cancel: () => void; refresh: () => Promise<void> }) {
  const [f, setF] = useState<Form>(() => (watch ? fromWatch(watch) : blank('')));
  const [busy, setBusy] = useState<null | 'save' | 'activate' | 'snapshot'>(null);
  const [error, setError] = useState<string | null>(null);
  const [stamp, setStamp] = useState(0);
  const [hasSnap, setHasSnap] = useState<Record<string, boolean>>(() => Object.fromEntries(boot.cameras.map((c) => [c.id, c.hasSnapshot])));
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((p) => ({ ...p, [k]: v }));
  const cam = boot.cameras.find((c) => c.id.toLowerCase() === f.cameraId.toLowerCase());
  const cap = boot.capabilities.find((c) => c.id === f.detectorId);
  const snapUrl = cam ? `/api/cameras/${cam.id.toLowerCase()}/snapshot?t=${stamp}` : '';
  const prompt = useMemo(() => f.instruction.trim() ? `Assess whether the following is directly visible: ${f.instruction.trim().replace(/\.$/, '')}. …` : '', [f.instruction]);

  const snapshot = async () => {
    if (!cam) return;
    setBusy('snapshot'); setError(null);
    try { await api.post(`/api/cameras/${cam.id.toLowerCase()}/snapshot`, {}); setHasSnap((p) => ({ ...p, [cam.id]: true })); setStamp(Date.now()); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Could not take a snapshot.'); }
    finally { setBusy(null); }
  };
  const save = async (activate: boolean) => {
    setBusy(activate ? 'activate' : 'save'); setError(null);
    try {
      let w: Watch;
      if (watch) w = await api.put<Watch>(`/api/watches/${watch.id}`, { baseVersion: watch.version, config: payload(f) });
      else w = await api.post<Watch>('/api/watches', payload(f));
      if (activate) w = await api.post<Watch>(`/api/watches/${w.id}/status`, { status: 'active', baseVersion: w.version });
      await refresh();
      done(w.id);
    } catch (e) { setError(e instanceof ApiError ? e.message : 'The Watch was not saved.'); }
    finally { setBusy(null); }
  };
  const native: WatchConfig['native'] | null = cam ? { event: 'Adaptive Watch Review Required', alarm: cam.native } : null;

  return (
    <div className="editor">
      <form className="editor-form" onSubmit={(e) => e.preventDefault()} aria-label={watch ? 'Edit Watch' : 'Create Watch'}>
        <header className="page-head tight"><div><h1>{watch ? `Edit “${watch.config.name}”` : 'Create a Watch'}</h1>
          <p className="sub">{watch ? `Saving creates version ${watch.version + 1}. Assessments already completed keep the exact settings they used.` : 'A Watch points a guardian at one camera: a question for Hafnia, a local vision check, and when to raise an exception.'}</p></div></header>

        <section className="step"><h2><span>1</span>Camera</h2>
          <label className="field"><span>Authorized XProtect camera</span>
            <select value={f.cameraId} onChange={(e) => { set('cameraId', e.target.value); set('region', null); }} disabled={!!watch && watch.jobs.length > 0 && false}>
              <option value="">Choose a camera…</option>
              {boot.cameras.map((c) => <option key={c.id} value={c.id}>{cameraLabel(c.name)}</option>)}
            </select></label>
          {cam && <p className="hint mono">{cam.id.toLowerCase()}</p>}
        </section>

        <section className="step"><h2><span>2</span>The question for Hafnia</h2>
          <label className="field"><span>Name this Watch</span><input value={f.name} onChange={(e) => set('name', e.target.value)} maxLength={60} placeholder="Platform edge" /></label>
          <label className="field"><span>What should Hafnia look for?</span>
            <textarea value={f.instruction} onChange={(e) => set('instruction', e.target.value)} rows={3} maxLength={500} placeholder="A person climbs down from the platform edge onto the track area" />
            <small>Describe what should be visible, in plain words. Ortru adds the fixed answer format. {f.instruction.length}/500</small></label>
          <label className="field"><span>Name the visible condition</span><input value={f.condition} onChange={(e) => set('condition', e.target.value)} maxLength={60} placeholder="Person on the track area" />
            <small>Used for the review question the operator answers: “Is {f.condition ? `“${f.condition}”` : 'this condition'} visible in the footage?”</small></label>
          {prompt && <details className="adv"><summary>Exact request sent to Hafnia</summary><p className="quote">{prompt}</p></details>}
        </section>

        <section className="step"><h2><span>3</span>What local vision watches</h2>
          <div className="caps" role="radiogroup" aria-label="Local vision capability">
            {boot.capabilities.map((c) => (
              <label key={c.id} className={`cap${f.detectorId === c.id ? ' on' : ''}${c.available ? '' : ' off'}`}>
                <input type="radio" name="cap" value={c.id} checked={f.detectorId === c.id} disabled={!c.available} onChange={() => set('detectorId', c.id)} />
                <b>{c.label}</b>
                {c.available ? <span>{c.establishes}</span> : <span className="why">Not available: {c.reason}</span>}
              </label>
            ))}
          </div>
          {cap?.needsRegion && <p className="hint">Draw the region on the camera picture to the right. It is saved with this Watch.</p>}
          <details className="adv"><summary>Detector settings</summary>
            {cap && Object.entries(cap.parameters).map(([k, p]) => (
              <label key={k} className="field"><span>{p.label}</span>
                <input type="number" step="0.01" min={p.min} max={p.max} value={f.margin} onChange={(e) => set('margin', Number(e.target.value))} /></label>
            ))}
            {cap && <p className="hint">{cap.model}. {cap.cannot}</p>}
          </details>
        </section>

        <section className="step"><h2><span>4</span>When to raise an exception</h2>
          <fieldset className="raise"><legend className="sr-only">Signal combinations that raise an exception</legend>
            {boot.policyKinds.filter((k) => RAISE_HELP[k.id]).map((k) => (
              <label key={k.id} className="check"><input type="checkbox" checked={f.raiseOn.includes(k.id)} onChange={(e) => set('raiseOn', e.target.checked ? [...f.raiseOn, k.id] : f.raiseOn.filter((x) => x !== k.id))} />{RAISE_HELP[k.id]}</label>
            ))}
          </fieldset>
          <p className="hint">A “no” from Hafnia alongside a person at the region is not a contradiction: the two are separate observers. An unsure or unreadable Hafnia answer is never treated as “no”.</p>
        </section>

        <section className="step"><h2><span>5</span>How often</h2>
          <div className="pair">
            <label className="field"><span>Look at a recorded window</span>
              <select value={f.intervalMinutes} onChange={(e) => set('intervalMinutes', Number(e.target.value))}>{CADENCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label className="field"><span>Hafnia requests per day, at most</span><input type="number" min={1} max={100} value={f.perDay} onChange={(e) => set('perDay', Number(e.target.value))} /></label>
          </div>
          <details className="adv"><summary>Recording window</summary>
            <label className="field"><span>Seconds of recording per assessment (12 to 17)</span><input type="number" min={12} max={17} value={f.windowSeconds} onChange={(e) => set('windowSeconds', Number(e.target.value))} /></label>
          </details>
          <p className="hint">Ortru samples recorded windows at this cadence. It does not stream live video, and it never asks Hafnia more often than this budget allows.</p>
        </section>

        <section className="step"><h2><span>6</span>XProtect</h2>
          {!native ? <p className="hint">Choose a camera to see its XProtect destination.</p>
            : native.alarm ? <Notice tone="good" title="Alarm ready">Exceptions can be sent as “{native.event}”, raising “{native.alarm}” in Smart Client. Every send needs your confirmation.</Notice>
            : <Notice tone="review" title="No XProtect alarm for this camera yet">You can review exceptions without it. To send them to XProtect, an event and a camera alarm must be added in XProtect, which changes the VMS and needs your explicit approval first.</Notice>}
        </section>

        {error && <Notice tone="bad" title="Not saved">{error}</Notice>}
        <div className="editor-actions">
          <button type="button" className="quiet" onClick={cancel}>Cancel</button><span className="grow" />
          <button type="button" className="quiet" disabled={busy !== null} onClick={() => save(false)}>{busy === 'save' ? 'Saving…' : watch ? 'Save version' : 'Save as draft'}</button>
          <button type="button" className="primary" disabled={busy !== null} onClick={() => save(true)}>{busy === 'activate' ? 'Activating…' : watch ? 'Save and activate' : 'Save and activate'}</button>
        </div>
      </form>

      <aside className="editor-camera" aria-label="Camera picture">
        {!cam ? <div className="snap-empty"><p>Choose a camera to see it here.</p></div>
          : hasSnap[cam.id] ? <RegionDrawer src={snapUrl} region={f.region} onChange={(r) => set('region', r)} readOnly={!cap?.needsRegion} />
          : <div className="snap-empty"><p>No picture of {cameraLabel(cam.name)} has been taken yet.</p></div>}
        {cam && <div className="snap-actions"><button type="button" className="quiet" onClick={snapshot} disabled={busy === 'snapshot'}>{hasSnap[cam.id] ? 'Take a fresh picture' : 'Take a picture'}</button>
          <span className="hint">A recorded frame from the last minutes, read only.</span>{busy === 'snapshot' && <Spinner label="Reading the recording…" />}</div>}
        {cam && cap?.needsRegion && <Chip tone={f.region && f.region.polygon.length >= 3 ? 'good' : 'review'}>{f.region && f.region.polygon.length >= 3 ? 'Region drawn' : 'Region needed'}</Chip>}
      </aside>
    </div>
  );
}
