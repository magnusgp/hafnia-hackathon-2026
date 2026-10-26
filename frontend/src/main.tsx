import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/space-grotesk/600.css";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./style.css";

type Run = {
  first: string;
  last: string;
  samples: number;
  sampled_span_s: number;
  min_box_overlap: number;
};
type RecordSummary = {
  id: string;
  title: string;
  camera: string;
  interval: string[];
  evidenceKind: string;
  status: string;
  operatorAction: string;
  alarmStatus: string;
  runs: Run[];
  state: string;
  observationCount: number;
};
type Evidence = RecordSummary & {
  observations: { observationId: string; interval: string[]; manifestSha256: string }[];
  decisions: { id: string; action: string; at: string; note: string }[];
  frames: { file: string; timestamp: string; box: number[] | null }[];
  cameraGuid: string;
  manifestSha256: string;
  cvSha256: string;
  joinedSha256: string;
  hafnia: {
    summary_id: string;
    original_response: string;
    parsed: { evidence?: string; outcome: string; limitations?: string };
    repair_provenance: string[];
  }[];
  limitations: string[];
  polygon: number[][];
  geometryApproved: boolean;
  dispatchReviewReady: boolean;
};
type Workspace = {
  cameras: { id: string; name: string; configured: boolean; role: string }[];
  records: RecordSummary[];
  sources: string[];
};
const label = (s: string) => s.replaceAll("_", " ");
const stateLabel = (s: string) => s === "escalated" ? "Transport accepted ? alarm unverified" : s === "review_required" ? "Review saved" : label(s);
const clock = (s: string) => s.slice(11, 23);
async function read<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal });
  if (!r.ok)
    throw Error(
      `Evidence API returned ${r.status}. Check the localhost evidence server and incident ID.`,
    );
  return r.json();
}
async function mutate(url: string, body: unknown): Promise<Response> {
  const session = await read<{csrf:string}>('/api/session');
  return fetch(url, {method:'POST', headers:{'Content-Type':'application/json','X-AW-CSRF':session.csrf}, body:JSON.stringify(body)});
}
function Tag({
  children,
  review = false,
}: {
  children: React.ReactNode;
  review?: boolean;
}) {
  return <span className={`tag ${review ? "review" : ""}`}>{children}</span>;
}
function Investigation({ e: initial, demoSession, onSaved }: { e: Evidence; demoSession?: string; onSaved: () => void }) {
  const [e, setEvidence] = useState(initial);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setEvidence(previous => {
      if (previous.observations.map(o=>o.observationId).sort().join() !== initial.observations.map(o=>o.observationId).sort().join()) {
        setDecision("Evidence changed: another observation joined this incident. Review the updated evidence before saving.");
      }
      return initial;
    });
  }, [initial]);
  async function decide(action: string) {
    setDecision("");
    setSaving(true);
    try {
      const r = await mutate(`/api/incidents/${e.id}/decisions`, {action,note,demoSession,evidence:e.observations.map(o=>o.observationId).sort()});
      if (r.status === 409) {
        setEvidence(await read<Evidence>(`/api/incidents/${e.id}`));
        onSaved();
        setDecision("Decision was not saved (HTTP 409). Evidence or incident state changed. Updated evidence loaded; review it and choose again.");
        return;
      }
      if (!r.ok) throw Error(`Decision was not saved (HTTP ${r.status}). Please retry.`);
      setEvidence(await r.json());
      onSaved();
      setDecision(action === "dismiss" ? "Incident dismissed. Retained in history." : "Review saved.");
    } catch (err) {setDecision(String(err));} finally {setSaving(false);}
  }
  const [semantic, setSemantic] = useState(0);
  const [index, setIndex] = useState(
    Math.max(
      0,
      e.frames.findIndex((f) => f.box !== null),
    ),
  );
  const [playing, setPlaying] = useState(false),
    [overlay, setOverlay] = useState(true),
    [zone, setZone] = useState(false),
    [note, setNote] = useState(""),
    [decision, setDecision] = useState("");
  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(
      () =>
        setIndex((i) => {
          if (i >= e.frames.length - 1) {
            setPlaying(false);
            return i;
          }
          return i + 1;
        }),
      1000,
    );
    return () => clearInterval(t);
  }, [playing, e.frames.length]);
  const f = e.frames[index],
    run = e.runs[0];
  const seek = (n: number) => {
    setPlaying(false);
    setIndex(n);
  };
  return (
    <>
      <div className="investigation-grid">
        <section className="panel evidence">
          <div className="section-heading compact">
            <div>
              <span className="eyebrow">XPROTECT SOURCE FRAMES</span>
              <p className="camera-name">{label(e.camera)}</p>
            </div>
            <code>{clock(f.timestamp)} UTC</code>
          </div>
          <div className="video-stage">
            <div className="frame">
              <img
                src={f.file}
                alt={`Original XProtect sample from ${label(e.camera)}`}
              />
              <svg
                viewBox="0 0 1000 1000"
                preserveAspectRatio="none"
                aria-label="Evidence localization"
              >
                {zone && (
                  <polygon
                    points={e.polygon
                      .map((p) => p.map((v) => v * 1000).join(","))
                      .join(" ")}
                    fill="var(--aw-review)"
                    fillOpacity=".15"
                    stroke="var(--aw-review)"
                    strokeDasharray="8 5"
                    strokeWidth="2"
                  />
                )}
                {overlay && f.box && (
                  <rect
                    x={f.box[0] * 1000}
                    y={f.box[1] * 1000}
                    width={(f.box[2] - f.box[0]) * 1000}
                    height={(f.box[3] - f.box[1]) * 1000}
                    fill="none"
                    stroke="var(--aw-primary)"
                    strokeWidth="3"
                  />
                )}
              </svg>
              {overlay && f.box && (
                <span
                  className="box-label"
                  style={{
                    left: `${f.box[0] * 100}%`,
                    top: `${f.box[1] * 100}%`,
                  }}
                >
                  Selected CV object
                </span>
              )}
            </div>
          </div>
          <div className="transport">
            <button
              className="button secondary"
              onClick={() => {
                if (index === e.frames.length - 1) setIndex(0);
                setPlaying(!playing);
              }}
            >
              {playing ? "Pause" : "Play samples"}
            </button>
            <input
              aria-label="Recording sample"
              type="range"
              min="0"
              max={e.frames.length - 1}
              value={index}
              onChange={(ev) => seek(+ev.target.value)}
            />
            <code>
              {index + 1} / {e.frames.length}
            </code>
          </div>
          <div className="evidence-options">
            <label>
              <input
                type="checkbox"
                checked={overlay}
                onChange={(ev) => setOverlay(ev.target.checked)}
              />{" "}
              Selected CV box
            </label>
            <label>
              <input
                type="checkbox"
                checked={zone}
                onChange={(ev) => setZone(ev.target.checked)}
              />{" "}
              {e.geometryApproved
                ? "Reviewed region"
                : "Draft region · unapproved"}
            </label>
          </div>
          <p className="sample-disclosure">
            Timestamped samples; continuity between frames is unknown.
            Continuous footage is not bundled for this interval.
          </p>
          <div className="sequence">
            <div className="eyebrow">SOURCE TIMELINE / UTC</div>
            <div>
              {[
                0,
                Math.max(
                  0,
                  e.frames.findIndex((frame) => frame.box),
                ),
                e.frames.length - 1,
              ].map((n, i) => (
                <button key={i} onClick={() => seek(n)}>
                  <time>{clock(e.frames[n].timestamp)}</time>
                  <span>
                    {
                      [
                        "First sample",
                        "Selected stationary candidate",
                        "Final sample",
                      ][i]
                    }
                  </span>
                </button>
              ))}
            </div>
          </div>
        </section>
        <aside className="panel interpretation">
          <div className="eyebrow">INCIDENT / {e.id.slice(0, 8)}</div>
          <Tag review>{stateLabel(e.state)}</Tag>
          <section className="operator">
            <div className="source-heading">OPERATOR ACTION</div>
            <h2>Decision</h2>
            <label className="sr-only" htmlFor="note">
              Review note
            </label>
            <textarea
              id="note"
              maxLength={4000}
              value={note}
              onChange={(ev) => setNote(ev.target.value)}
              placeholder="Session review note…"
            />
            <div className="evidence-options">
              <button className="button" disabled={saving || ["dismissed","escalated"].includes(e.state)} onClick={() => decide("review_required")}>Save review</button>
              <button className="button secondary" disabled={saving || ["dismissed","escalated"].includes(e.state)} onClick={() => decide("dismiss")}>Dismiss incident</button>

            </div>
            {decision && <p role="status">{decision}</p>}
            <NativeAction evidence={e.observations.map(o=>o.observationId).sort()} incident={e.id} revision={JSON.stringify([e.observations.map(o=>o.observationId),e.state])} replay={e.evidenceKind === "replay"} />
            {!e.geometryApproved && <p>Dispatch blocked: pedestrian region needs approval.</p>}
            {!e.dispatchReviewReady && e.geometryApproved && <p>Dispatch blocked: verified fresh evidence requirements are incomplete. Review technical details.</p>}
            <details><summary>{e.observationCount} observations &middot; {e.decisions.length} saved decisions</summary>
              {e.observations.map(o=><p key={o.observationId}>{o.interval.join(" to ")}</p>)}
              {e.decisions.map(d=><p key={d.id}>{label(d.action)} &middot; {d.at} &middot; {d.note}</p>)}
            </details>
          </section>
          <section>
            <h2>Object remains in place</h2>
            {run ? (
              <>
                <div className="measure">
                  {run.sampled_span_s.toFixed(1)}
                  <span>seconds / {run.samples} samples</span>
                </div>
                <p>
                  {clock(run.first)}–{clock(run.last)} UTC
                </p>
                <div className="overlap">
                  <strong>{(run.min_box_overlap * 100).toFixed(1)}%</strong>{" "}
                  minimum box overlap with region
                </div>
              </>
            ) : (
              <p>No qualifying stationary run.</p>
            )}
            <small>
              Image-space stationarity and box overlap do not establish
              pedestrian clearance.
            </small>
          </section>
          <section>
            <div className="source-heading">HAFNIA INTERPRETATION</div>
            <label className="semantic-picker">
              Saved assessment{" "}
              <select
                aria-label="Hafnia assessment"
                value={semantic}
                onChange={(ev) => setSemantic(+ev.target.value)}
              >
                {e.hafnia.map((h, i) => (
                  <option key={h.summary_id} value={i}>
                    Response {i + 1}
                  </option>
                ))}
              </select>
            </label>
            {e.hafnia[semantic] && (
              <div className="semantic-result">
                <Tag>{e.hafnia[semantic].parsed.outcome}</Tag>
                <p>
                  {e.hafnia[semantic].parsed.evidence ||
                    "No valid semantic evidence available."}
                </p>
              </div>
            )}
          </section>
        </aside>
      </div>

      <details className="panel provenance">
        <summary>
          Evidence & provenance{" "}
          <span>Source identity, model responses and limitations</span>
        </summary>
        <dl>
          {Object.entries({
            "Incident ID": e.id,
            "Camera GUID": e.cameraGuid,
            "Source interval": e.interval.join(" → "),

          }).map(([k, v]) => (
            <React.Fragment key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </React.Fragment>
          ))}
        </dl>
        {e.hafnia.map((h) => (
          <details key={h.summary_id}>
            <summary>Hafnia / {h.summary_id}</summary>
            <p>Normalization: {h.repair_provenance.join(", ") || "none"}</p>
            <pre>{h.original_response}</pre>
            <p>{h.parsed.limitations}</p>
          </details>
        ))}
        <details>
          <summary>Detailed limitations</summary>
          <ul>
            {e.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </details>
      </details>
    </>
  );
}
type NativeStatus = {available:boolean; state:string; reason?:string; destination?:string};
type Confirmation = {token:string; title:string; camera:string; interval:string[]; destination:string; action:string; consequence:string};
function NativeAction({incident,revision,replay,evidence}:{incident:string;revision:string;replay:boolean;evidence:string[]}) {
  const [status,setStatus] = useState<NativeStatus | null>(null);
  const [confirmation,setConfirmation] = useState<Confirmation | null>(null);
  const [checked,setChecked] = useState(false), [busy,setBusy] = useState(false), [error,setError] = useState('');
  useEffect(()=>{setConfirmation(null);setChecked(false);read<NativeStatus>(`/api/incidents/${incident}/native-action`).then(setStatus).catch(()=>setStatus({available:false,state:'unavailable',reason:'Native status unavailable.'}));},[incident,revision]);
  async function act(action:string) {
    setBusy(true);setError('');
    try {
      const response = await mutate(`/api/incidents/${incident}/native-action/${action}`, action==='prepare'?{evidence}:{token:confirmation?.token,confirmed:checked});
      if (!response.ok) {setStatus(await read<NativeStatus>(`/api/incidents/${incident}/native-action`)); throw Error(`XProtect action was not completed (HTTP ${response.status}). Evidence or availability changed; review again.`);}
      const result = await response.json();
      if (action==='prepare') {setConfirmation(result);setChecked(false);} else {setStatus(result);setConfirmation(null);}
    } catch(err) {setError(String(err));setConfirmation(null);} finally {setBusy(false);}
  }
  return <section className="panel native-action"><strong>Native XProtect action</strong>
    <p role="status">{replay ? 'Unavailable in replay' : status?.reason || (status?.available ? `Ready for confirmation: ${status.destination}` : 'Checking availability...')}</p>
    {status?.available && !replay && <button className="button" disabled={busy} onClick={()=>act('prepare')}>Escalate to XProtect</button>}
    {error && <p role="alert">{error}</p>}
    {confirmation && <div className="confirmation-backdrop"><section className="panel confirmation" role="dialog" aria-modal="true" aria-label="Confirm XProtect escalation">
      <h2>Confirm XProtect escalation</h2><p>{confirmation.action}</p><h3>{confirmation.title}</h3>
      <p>{label(confirmation.camera)}<br/>{confirmation.interval.join(' to ')} UTC</p><p>Destination: {confirmation.destination}</p><p>{confirmation.consequence}</p>
      <label><input type="checkbox" checked={checked} onChange={ev=>setChecked(ev.target.checked)}/> I reviewed this incident and authorize this event.</label>
      <div className="evidence-options"><button className="button" disabled={!checked || busy} onClick={()=>act('confirm')}>Confirm and send to XProtect</button><button className="button secondary" disabled={busy} onClick={()=>setConfirmation(null)}>Cancel</button></div>
    </section></div>}
  </section>;
}
type Replay = {session: string; mode: string; cursor: number; total: number; complete: boolean; provenance: string};
function App() {
  const [replay, setReplay] = useState<Replay | null>(null);
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayError, setReplayError] = useState("");
  const [running, setRunning] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setRevision(r=>r+1), 2000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => { fetch('/api/demo').then(r => r.ok ? r.json() : null).then(setReplay); }, [revision]);
  async function replayAction(action: string) {
    setReplayBusy(true);
    try {
      const response = await mutate(`/api/demo/${action}`, {cursor: replay?.cursor, demoSession: replay?.session});
      if (!response.ok) {setReplay(await read<Replay>('/api/demo')); throw Error(`Replay action was not completed (HTTP ${response.status}). Current replay loaded; try again.`);}
      setReplayError('');
      const next = await response.json(); setReplay(next); setRevision(r => r + 1);
      if (next.complete || action === 'reset') setRunning(false);
      if (action === 'reset') location.hash = '#/demo';
    } catch (err) { setReplayError(String(err)); setRunning(false); } finally {setReplayBusy(false);}
  }
  useEffect(() => {
    if (!running || replayBusy || !replay || replay.complete) return;
    const timer = setTimeout(() => replayAction('next'), 1800);
    return () => clearTimeout(timer);
  }, [running, replayBusy, replay?.cursor]);
  const [path, setPath] = useState(location.hash),
    [w, setW] = useState<Workspace | null>(null),
    [e, setE] = useState<Evidence | null>(null),
    [error, setError] = useState("");
  const match = path.match(/^#\/investigation\/([a-f0-9]{24})$/),
    id = match?.[1],
    investigation = path.startsWith("#/investigation");
  useEffect(() => {
    const change = () => {setE(null); setPath(location.hash);};
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    const control = new AbortController();
    read<Workspace>("/api/incidents", control.signal)
      .then(setW)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => control.abort();
  }, [path, revision]);
  useEffect(() => {
    setError("");
    if (!id) return;
    const control = new AbortController();
    read<Evidence>(`/api/incidents/${id}`, control.signal)
      .then(setE)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => control.abort();
  }, [id, revision]);
  const visibleRecords = w?.records.filter(r=>path === "#/history" || !["dismissed","escalated"].includes(r.state)) || [];
  const mode = replay ? "Replay mode" : w?.records.some((r) => r.evidenceKind === "fresh_analysis")
    ? "Saved evidence + fresh analysis"
    : "Saved evidence";
  return (
    <>
      <header>
        <a className="wordmark" href="#/incidents">
          Adaptive Watch
        </a>
        <span className="product-label">XProtect incident qualification</span>
        <span className="local-label">{mode}</span>
      </header>
      <div className="shell">
        <nav aria-label="Main navigation">
          <div className="nav-caption">WORKSPACE</div>
          <a className={!investigation && !["#/demo","#/history"].includes(path) ? "active" : ""} href="#/incidents">
            <span>▦</span> Incidents
          </a>
          {replay && <a href="#/demo" className={path === "#/demo" ? "active" : ""}>Demo mode</a>}
          <a href="#/history" className={path === "#/history" ? "active" : ""}>Incident history</a>
          {id && (
            <a className="active" href={`#/investigation/${id}`}>
              <span>⌕</span> Investigation
            </a>
          )}
        </nav>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {investigation ? "INCIDENT INVESTIGATION" : path === "#/demo" ? "DEMO MODE" : "INCIDENTS"}
              </div>
              <h1>
                {investigation
                  ? e?.title || "Incident investigation"
                  : path === "#/history" ? "Incident history" : path === "#/demo" ? "Demo mode" : "Incidents"}
              </h1>
              <p>
                {investigation
                  ? e
                    ? `${label(e.camera)} · ${e.interval[0]} → ${clock(e.interval[1])} UTC`
                    : "Select a record from the review queue."
                  : path === "#/demo" ? "Replay of saved evidence; arrivals are synthetic." : "Review open incidents and retain decisions."}
              </p>
            </div>
            {e && investigation && (
              <Tag review>
                {e.evidenceKind === "fresh_analysis"
                  ? "Fresh analysis"
                  : e.evidenceKind === "replay" ? "Recorded evidence" : "Saved retrospective evidence"}
              </Tag>
            )}
          </div>
          {replay && path === "#/demo" && <section className="panel replay-controls" aria-label="Replay controls">
            <div className="section-heading"><div><h2>Replay controls</h2><p>{replay.cursor} / {replay.total} candidate observations &middot; {w?.records.length || 0} incidents</p></div>
            <div className="evidence-options">
            <button className="button" disabled={running || replayBusy || replay.complete} onClick={() => setRunning(true)}>{replay.cursor ? "Continue replay" : "Start replay"}</button>
            <button className="button secondary" disabled={!running} onClick={() => setRunning(false)}>Pause replay</button>
            <button className="button secondary" disabled={running || replayBusy || replay.complete} onClick={() => replayAction('next')}>Next observation</button>
            <button className="button secondary" disabled={running || replayBusy} onClick={() => replayAction('reset')}>New demo session</button></div></div>
            <details><summary>Replay evidence</summary><p>{replay.provenance}</p><p>No Hafnia requests or native events are available in replay. Previous sessions retain their saved decisions.</p></details>
          </section>}
          {replayError && <p role="alert">{replayError}</p>}
          {error ? (
            <section className="panel">
              <h2>Evidence unavailable</h2>
              <p>{error}</p>
              <a href="#/incidents">Return to incidents</a>
            </section>
          ) : !w ? (
            <p role="status">Loading evidence index…</p>
          ) : investigation ? (
            e ? (
              <Investigation key={e.id} e={e} demoSession={replay?.session} onSaved={()=>setRevision(r=>r+1)} />
            ) : id ? (
              <p role="status">Loading incident…</p>
            ) : (
              <a className="button" href="#/incidents">
                Open review queue
              </a>
            )
          ) : (
            <>
              <section className="panel incidents">
                <div className="section-heading">
                  <div>
                    <h2>{path === "#/history" ? "Incident history" : "Open incidents"}</h2>
                  </div>
                  <span className="muted">
                    {visibleRecords.length} incidents
                  </span>
                </div>
                <div className="incident-list">
                  {visibleRecords.map((r) => (
                    <article key={r.id}>
                      <div>
                        <h3>{r.title}</h3>
                        <small>{label(r.camera)}</small>
                        <time>First: {r.interval[0]}<br />Latest: {r.interval[1]}</time>
                      </div>
                      <div className="record-measure">
                        <strong>
                          {r.runs[0]
                            ? `${r.runs[0].sampled_span_s.toFixed(1)} s / ${r.runs[0].samples} samples`
                            : "No qualifying run"}
                        </strong>
                        <small>{r.operatorAction}</small>
                      </div>
                      <div><Tag review>{stateLabel(r.state)}</Tag><p>{r.observationCount === 1 ? "New incident" : `Existing incident \u00b7 ${r.observationCount} observations`}</p></div>
                      <a className="button" href={`#/investigation/${r.id}`}>
                        Investigate ↗
                      </a>
                    </article>
                  ))}
                </div>
                {visibleRecords.length === 0 && (
                  <p className="empty">
                    No open incidents. Demo mode can replay saved observations.
                  </p>
                )}
              </section>
              <details className="source-details">
                <summary>Workspace provenance</summary>
                {w.sources.map((s) => (
                  <p key={s}>{s}</p>
                ))}
                <p>
                  Configured camera subset; camera health and continuous
                  processing are not measured. Alarm verification is tracked
                  separately from model support.
                </p>
              </details>
            </>
          )}
        </main>
      </div>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
