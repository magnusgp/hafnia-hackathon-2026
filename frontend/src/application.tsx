import {useCallback, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {RailwayReview} from './railway-review';
import {clock,EvidenceDetails,ReviewControls,ReviewState,SnapshotEvidence,SourceInterval,type Sample} from './evidence-components';
import './workspace.css';

type CaseCard={id:string;title:string;camera:string;interval:string[];category:string;verificationRecommended:boolean;summary:string;evidence:string;state:{status:string;humanAnnotation:null|{value:string;note:string}}};
type Run={first:string;last:string;sampled_span_s:number;samples:number;max_anchor_drift:number;min_box_overlap:number};
type Hafnia={summary_id:string;request:{Prompt:string};original_response:string;parsed:{outcome:string;evidence:string;limitations:string}};
type CaseReview=CaseCard&{revision:string;frames:Sample[];hafnia:Hafnia[];runs:Run[];polygon:number[][]|null;model:string|null;limitations:string[];diagnostic?:{note:string;responses:{summaryId:string;prompt:string;response:string;interval:string[];family:string}[]}};
type Blocker={code:string;message:string;action:string};
type Options={cameras:{id:string;name:string;configuration:string}[];ready:boolean;blockers:Blocker[];catalogNote:string};
async function request(path:string,body?:object,csrf?:string){
  const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json','X-Review-CSRF':csrf??''},body:JSON.stringify(body)}:undefined);
  const result=await r.json();if(!r.ok)throw new Error(result.error??'Request failed');return result;
}
function Header({onBack,children}:{onBack?:()=>void;children?:React.ReactNode}){
  return <header className="top"><span className="wordmark">Adaptive Watch<span className="brand-dot"/></span><span>Evidence verification</span>{onBack&&<button className="text-button" onClick={onBack}>All assessments</button>}{children}</header>;
}
function Investigation({id,onBack}:{id:string;onBack:()=>void}){
  const [review,setReview]=useState<CaseReview|null>(null),[csrf,setCsrf]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[details,setDetails]=useState(false);
  const close=useCallback(()=>setDetails(false),[]);
  const load=useCallback(async()=>{const r=await request(`/api/cases/${id}`);setReview(r.review);setCsrf(r.csrf);},[id]);
  useEffect(()=>{load().catch(e=>setError(e.message));},[load]);
  async function act(action:string,body:object){
    if(!review)return false;setBusy(true);setError('');
    try{const r=await request(`/api/cases/${id}/action`,{action,revision:review.revision,...body},csrf);setReview(r.review);return true;}
    catch(e){setError((e as Error).message);try{await load();}catch{setReview(null);}return false;}finally{setBusy(false);}
  }
  if(!review)return <><Header onBack={onBack}/><main className="loading"><h1>Assessment unavailable</h1><p role="alert">{error||'Verifying original evidence…'}</p></main></>;
  const run=review.runs[0];
  return <><Header onBack={onBack}><button className="text-button" data-details onClick={()=>setDetails(true)}>Evidence details</button></Header><main>
    <div className="case-heading"><div><p className="eyebrow">{review.category}</p><h1>{review.title}</h1><SourceInterval camera={review.camera} interval={review.interval}/></div><ReviewState status={review.state.status}/></div>
    {error&&<p className="error" role="alert">{error}</p>}
    <div className="workspace"><SnapshotEvidence frames={review.frames} polygon={review.polygon} subject={id==='gate'?'School gate':id==='bin'?'Bin':'Scooter'} onError={()=>{setReview(null);setError('Original sample unavailable or failed source verification. Restore this case’s source evidence before reviewing.');}}/>
      <aside><section className="assessment"><p className="eyebrow">Hafnia assessment</p><h2>{id==='gate'?'Original negative conclusion':'Left object supported'}</h2><blockquote>{review.hafnia[0].parsed.evidence}</blockquote><button className="text-button" onClick={()=>setDetails(true)}>Compare original responses ↗</button></section>
        <section className="observation"><p className="eyebrow">{run?'Independent CV observation':'Independent evidence unavailable'}</p><h2>{run?`${run.sampled_span_s.toFixed(1)} s sampled stationarity`:'Semantic uncertainty'}</h2>{run?<><p>{clock(run.first)}–{clock(run.last)} UTC · {run.samples} samples</p><dl className="measurements"><dt>Maximum center drift</dt><dd>{run.max_anchor_drift.toFixed(5)} image units</dd><dt>Minimum box/walkway overlap</dt><dd>{(run.min_box_overlap*100).toFixed(1)}%</dd></dl><p className="meaning">Draft walkway. Partial box overlap does not establish obstruction or accessible clearance.</p></>:<><p>The responses describe manipulation while returning a negative outcome because opening is not observed. No independent local CV corroborates it.</p><p className="meaning">Opening, entry, damage and intent remain unestablished.</p></>}</section>
        <ReviewControls key={review.revision+review.state.status} status={review.state.status} busy={busy} saved={review.state.humanAnnotation} act={act}/>
      </aside></div>
    <p className="source-note">{review.evidence} Operator verification recommended. Original acquisition dates are preserved.</p>
    </main>{details&&<EvidenceDetails onClose={close}><h3>Source identity</h3><SourceInterval camera={review.camera} interval={review.interval}/><h3>Original Hafnia responses</h3>{review.hafnia.map(h=><details key={h.summary_id} open><summary>{h.parsed.outcome.replaceAll('_',' ')} · Summary {h.summary_id}</summary><p>{h.request.Prompt}</p><pre>{h.original_response}</pre></details>)}
      {run&&<><h3>Timestamped local CV measurements</h3><p>{review.model}. Bounded sampled image-center drift; no claim between samples or after the last sample.</p><table><thead><tr><th>First UTC</th><th>Last UTC</th><th>Span</th><th>Samples</th></tr></thead><tbody>{review.runs.map(r=><tr key={r.first}><td>{clock(r.first)}</td><td>{clock(r.last)}</td><td>{r.sampled_span_s} s</td><td>{r.samples}</td></tr>)}</tbody></table></>}
      <h3>Limitations</h3><ul>{review.limitations.map(l=><li key={l}>{l}</li>)}</ul>
      {review.state.humanAnnotation&&<><h3>Saved operator annotation</h3><p>{review.state.humanAnnotation.value.replaceAll('_',' ')} · {review.state.humanAnnotation.note}</p></>}
      {review.diagnostic&&<><h3>Separate prompt diagnostic · 27 October</h3><p>{review.diagnostic.note}</p><p>These prompt variants use one later recording. They are not independent events and have no CV corroboration.</p>{review.diagnostic.responses.map(r=><details key={r.summaryId}><summary>{r.family} · {r.interval[0].slice(0,10)} {clock(r.interval[0])}–{clock(r.interval[1])} UTC</summary><p>Summary {r.summaryId}</p><p>{r.prompt}</p><pre>{r.response}</pre></details>)}</>}
    </EvidenceDetails>}</>;
}
function NewAssessment({onBack}:{onBack:()=>void}){
  const [options,setOptions]=useState<Options|null>(null),[csrf,setCsrf]=useState(''),[camera,setCamera]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [start,setStart]=useState(''),[end,setEnd]=useState(''),[attempt,setAttempt]=useState<{state:string;blockers:Blocker[]}|null>(null);
  useEffect(()=>{request('/api/assessments/options').then(r=>{setOptions(r);setCsrf(r.csrf);setCamera(r.cameras[0]?.id??'');}).catch(e=>setError(e.message));},[]);
  async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');setAttempt(null);try{const result=await request('/api/assessments',{cameraId:camera,start:start+'Z',end:end+'Z'},csrf);setAttempt(result.attempt);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <><Header onBack={onBack}/><main className="assessment-entry"><div className="case-heading"><div><p className="eyebrow">Existing XProtect recordings</p><h1>New assessment</h1><p>Select a camera and a past 12–17 second interval within the last 24 hours.</p></div></div>
    {error&&<p className="error" role="alert">{error}</p>}{!options&&!error&&<p role="status">Checking supported configurations…</p>}
    {options&&<div className="entry-grid"><form onSubmit={submit}><label className="field">Authorized camera<select aria-label="Authorized camera" value={camera} onChange={e=>setCamera(e.target.value)}>{options.cameras.map(c=><option value={c.id} key={c.id}>{c.name}</option>)}</select></label><p className="source-note">{options.catalogNote}</p><label className="field">Analysis configuration<input readOnly value="Persistent sidewalk object · Hafnia + local CV"/></label><label className="field">Recording start (UTC)<input type="datetime-local" step="1" required value={start} onChange={e=>setStart(e.target.value)}/></label><label className="field">Recording end (UTC)<input type="datetime-local" step="1" required value={end} onChange={e=>setEnd(e.target.value)}/></label><button className="primary" disabled={busy||!camera}>{busy?'Checking runtime readiness…':'Start assessment'}</button><p className="source-note">Readiness must pass before acquisition or inference can begin.</p></form>
      <section className="runtime-panel" aria-label="Assessment runtime"><p className="eyebrow">{attempt?'Assessment blocked':'Runtime preparation required'}</p><h2>{attempt?'Cannot start this assessment':'Analysis runtime is unavailable'}</h2><p>{attempt?'The server checked your selection. No recording was acquired and no Hafnia request was submitted.':'The current backend exposes a supervised analysis workflow. Its authenticated runtime is not attached to this web service.'}</p><div role={attempt?'status':undefined}>{(attempt?.blockers??options.blockers).map(b=><div className="blocker" key={b.code}><strong>{b.message}</strong><p>{b.action}</p></div>)}</div>{attempt&&<p className="meaning">This readiness failure was saved locally. It is not an assessment result. Ambiguous inference submissions are never automatically retried.</p>}</section></div>}
    </main></>;
}
function App(){
  const [route,setRoute]=useState(location.hash.slice(1)||'workspace');
  const [data,setData]=useState<{records:CaseCard[];unavailable:{id:string;error:string}[]}|null>(null),[error,setError]=useState('');
  useEffect(()=>{const change=()=>setRoute(location.hash.slice(1)||'workspace');addEventListener('hashchange',change);return()=>removeEventListener('hashchange',change);},[]);
  const navigate=(path:string)=>{location.hash=path;window.scrollTo({top:0});};
  const back=()=>navigate('workspace');
  const load=useCallback(()=>{setError('');return request('/api/workspace').then(setData).catch(e=>setError(e.message));},[]);
  useEffect(()=>{if(route==='workspace'){setData(null);load();}},[route,load]);
  if(route==='new')return <NewAssessment onBack={back}/>;
  if(route==='case/railway')return <RailwayReview onBack={back}/>;
  if(route.startsWith('case/'))return <Investigation key={route} id={route.slice(5)} onBack={back}/>;
  if(route!=='workspace')return <><Header onBack={back}/><main className="loading"><h1>Assessment unavailable</h1><p role="alert">Unknown workspace route. Return to all assessments to select verified evidence.</p></main></>;
  return <><Header><button className="new-button" onClick={()=>navigate('new')}>New assessment <span aria-hidden>＋</span></button></Header><main className="case-list">
    <div className="case-heading"><div><p className="eyebrow">Operator workspace</p><h1>Verify the evidence</h1><p>Compare the assessment with the available visual evidence, then record your decision.</p></div><button className="text-button" onClick={load}>Refresh sources</button></div>
    <div className="workspace-note"><span className="brand-dot"/><p>Saved source evidence · original dates and camera identities · local review decisions</p></div>
    {error&&<p className="error" role="alert">{error}</p>}{!data&&!error&&<p role="status">Verifying saved recording and assessment sources…</p>}
    {data&&<><div className="case-grid">{data.records.map(c=><article className="case-card" key={c.id} data-case={c.id}><div className="card-category"><span className={'evidence-category '+c.id}>{c.category}</span><ReviewState status={c.state.status}/></div><h2>{c.title}</h2><SourceInterval camera={c.camera} interval={c.interval}/><p className="actual-summary">{c.summary}</p><div className="available-evidence"><p className="eyebrow">Available evidence</p><p>{c.evidence}</p></div><div className="card-footer"><span>{c.verificationRecommended?'Operator verification recommended':'Verification optional'}</span><button onClick={()=>navigate('case/'+c.id)} aria-label={`Open ${c.id==='gate'?'school gate':c.id} investigation`}>Open investigation <span aria-hidden>↗</span></button></div></article>)}</div>{data.unavailable.length>0&&<section className="unavailable" role="alert"><h2>Source data unavailable</h2>{data.unavailable.map(c=><p key={c.id}><strong>{c.id}</strong> · {c.error}</p>)}</section>}{!data.records.length&&<p>No verified assessments are currently available. Restore the original source evidence and refresh.</p>}</>}
    <footer className="workspace-footer">Each case represents its saved source interval. Prompt variants and repeated scene loops are not independent events. No native XProtect event is sent by this workspace.</footer>
  </main></>;
}
createRoot(document.getElementById('root')!).render(<App/>);
