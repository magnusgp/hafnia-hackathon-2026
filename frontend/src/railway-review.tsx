import React, {useEffect, useRef, useState} from 'react';
import '@fontsource/space-grotesk/600.css';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/ibm-plex-mono/400.css';
import './negative-review.css';
import {EvidenceDetails,SourceInterval} from './evidence-components';

type Frame = {index:number;timestamp:string;mediaTime:number;box:number[]|null;file:string;distance:number|null;proximity:boolean};
type Region = {polygon:number[][];threshold:number};
type Review = {
  revision:string;camera:string;cameraGuid:string;interval:string[];reason:string;frames:Frame[];trigger:Frame|null;
  state:{status:string;region:Region;reviewed:boolean;humanAnnotation:null|{value:string;note:string;at:string}};
  hafnia:{outcome:string;conclusion:string;summaryId:string;originalResponse:string;originalRequest:unknown};
  cv:{trackId:number;model:string;revision:string;limitation:string};media:{path:string;duration:number;source:string;timestampOrigin:string};
  reference:unknown;diagnostic:unknown;native:{eventName:string;configured:boolean;dispatchAvailable:boolean;reason:string};
  evidenceHashes:{name:string;sha256:string}[];
};
const clock = (utc:string) => utc.slice(11,23);
const labels:Record<string,string> = {review_required:'Review required',reviewing:'Review in progress',dismissed:'Dismissed',xprotect_review_requested:'Review request saved locally'};

export function RailwayReview({onBack}:{onBack?:()=>void}){
  const [review,setReview] = useState<Review|null>(null), [csrf,setCsrf] = useState('');
  const [error,setError] = useState(''), [busy,setBusy] = useState(false), [details,setDetails] = useState(false);
  const [frameIndex,setFrameIndex] = useState(0), [seeking,setSeeking] = useState(false), [overlay,setOverlay] = useState(true);
  const [annotation,setAnnotation] = useState('not_verified'),[note,setNote] = useState(''),[ack,setAck] = useState(false);
  const [polygon,setPolygon] = useState(''),[threshold,setThreshold] = useState(0);
  const [drawing,setDrawing] = useState(false),[draft,setDraft] = useState<number[][]>([]);
  const video = useRef<HTMLVideoElement>(null);
  const load = async()=>{
    const response=await fetch('/api/review'); const result=await response.json();
    if(!response.ok)throw new Error(result.error);
    setReview(result.review);setCsrf(result.csrf);
    setPolygon(JSON.stringify(result.review.state.region.polygon));setThreshold(result.review.state.region.threshold);
  };
  useEffect(()=>{load().catch(e=>setError(e.message));},[]);
  useEffect(()=>{
    const v=video.current;if(!v||!review)return;
    let handle=0,active=true;
    const tick=(_:number,meta:VideoFrameCallbackMetadata)=>{
      if(!active)return;
      setFrameIndex(Math.min(review.frames.length-1,Math.max(0,Math.floor(meta.mediaTime*2+.0001))));
      handle=v.requestVideoFrameCallback(tick);
    };
    handle=v.requestVideoFrameCallback(tick);
    return()=>{active=false;v.cancelVideoFrameCallback(handle);};
  },[review?.media.path]);
  async function act(action:string,extra:object={}){
    if(!review)return;setBusy(true);setError('');
    try{
      const response=await fetch('/api/review/action',{method:'POST',headers:{'Content-Type':'application/json','X-Review-CSRF':csrf},body:JSON.stringify({action,revision:review.revision,...extra})});
      const result=await response.json();
      if(!response.ok){if(response.status===409){await load();setAck(false);}throw new Error(result.error);}
      setReview(result.review);return true;
    }catch(e){setError((e as Error).message);return false;}finally{setBusy(false);}
  }
  function seek(time:number){const v=video.current;if(v){v.currentTime=time;setFrameIndex(Math.floor(time*2));}}
  async function begin(){if(await act('review')){seek(0);await video.current?.play().catch(()=>{});}}
  async function decide(action:string){video.current?.pause();await act(action,{annotation,note,footageReviewed:ack});}
  if(!review)return <main className="loading"><h1>Adaptive Watch</h1><p role="alert">{error||'Loading saved railway evidence…'}</p></main>;
  const current=review.frames[frameIndex],box=current?.box;
  const finished=['dismissed','xprotect_review_requested'].includes(review.state.status);
  const start=review.state.status==='review_required';
  const timeline=[{at:0,label:'Interval start'},{at:review.trigger?.mediaTime??5.5,label:'Proximity observation'},{at:9.5,label:'Later footage'}];
  return <>
    <header className="top"><span className="wordmark">Adaptive Watch<span className="brand-dot"/></span><span>Footage review</span>{onBack&&<button className="text-button" onClick={onBack}>All assessments</button>}<button className="text-button" data-details onClick={()=>setDetails(true)}>Evidence details</button></header>
    <main>
      <div className="case-heading"><div><p className="eyebrow">Recorded railway case</p><h1>Check the platform edge</h1><SourceInterval camera={review.camera} interval={review.interval}/></div><div className={'state '+(finished?'resolved':'')} role="status"><span/> {labels[review.state.status]}</div></div>
      {error&&<p className="error" role="alert">{error}</p>}
      <div className="workspace">
        <section className="footage" aria-label="Recorded footage">
          <div className={'video-stage'+(drawing?' drawing':'')}>
            <video ref={video} src={review.media.path} controls={!drawing} preload="auto" playsInline
              onLoadedMetadata={()=>seek(review.trigger?.mediaTime??0)}
              onSeeking={()=>setSeeking(true)} onSeeked={()=>{setSeeking(false);setFrameIndex(Math.min(review.frames.length-1,Math.floor((video.current?.currentTime??0)*2+.0001)));}}
              aria-label="Original recorded railway snapshots at half-second intervals"/>
            {(overlay||drawing)&&<svg className="track-overlay" viewBox="0 0 832 480" aria-label={drawing?'Draw attention region':'Selected person track 7'} onClick={e=>{if(!drawing)return;const transform=e.currentTarget.getScreenCTM();if(!transform)return;const local=new DOMPoint(e.clientX,e.clientY).matrixTransform(transform.inverse());const point=[local.x/832,local.y/480];if(point.some(v=>v<0||v>1))return;setDraft(current=>current.length<4?[...current,point]:current);}}>
              <polygon points={(drawing?draft:review.state.region.polygon).map(p=>`${p[0]*832},${p[1]*480}`).join(' ')} fill="rgba(40,88,214,.06)" stroke="rgba(140,179,255,.9)" strokeWidth="1.5" strokeDasharray="6 5"/>
              {drawing&&draft.map((p,i)=><circle data-corner={i} key={i} cx={p[0]*832} cy={p[1]*480} r="4" fill="#FFD185"/>)}
              {!seeking&&box&&<g data-track="7" data-frame={frameIndex}><rect x={box[0]*832} y={box[1]*480} width={(box[2]-box[0])*832} height={(box[3]-box[1])*480} fill="none" stroke="#FFD185" strokeWidth="2"/><circle cx={(box[0]+box[2])/2*832} cy={box[3]*480} r="3" fill="#FFD185"/><rect x={box[0]*832} y={box[1]*480-22} width="70" height="22" rx="3" fill="#13263A"/><text x={box[0]*832+7} y={box[1]*480-7} fill="white" fontSize="12">Track 7</text></g>}
            </svg>}
          </div>
          {drawing&&<div className="draw-controls" role="status"><span>{draft.length<4?`Select four corners of the attention region (${draft.length}/4)`:'Four corners selected. Save to use this region.'}</span><button disabled={draft.length!==4||busy} onClick={async()=>{if(await act('configure_region',{region:{polygon:draft,threshold}})){setPolygon(JSON.stringify(draft));setDrawing(false);setAck(false);}}}>Save region</button><button onClick={()=>{setDrawing(false);setDraft([]);}}>Cancel</button></div>}
          <div className="media-caption"><span><span className="record-dot"/> Recorded footage · 0.5 s samples</span><time>{current&&clock(current.timestamp)} UTC</time></div>
          <div className="timeline" aria-label="Relevant moments">{timeline.map(t=><button key={t.label} onClick={()=>seek(t.at)}><span className="tick"/><span>{t.label}</span><time>+{t.at.toFixed(1)} s</time></button>)}</div>
          <div className="track-caption"><div><strong>Selected person · Track 7</strong><span>{box?'Bounding-box bottom shown on footage':'No selected-track detection in this sample'}</span></div><label><input type="checkbox" checked={overlay} onChange={e=>setOverlay(e.target.checked)}/> Show CV overlay</label></div>
        </section>
        <aside>
          <section className="assessment"><p className="eyebrow">Hafnia assessment</p><h2>Entry not observed</h2><blockquote>{review.hafnia.conclusion.split(/(?<=\.)\s/)[0]}</blockquote><button className="text-button" onClick={()=>setDetails(true)}>View original response <span aria-hidden>↗</span></button></section>
          <section className="observation"><p className="eyebrow">Independent CV observation</p><h2>{review.trigger?'Person near attention region':'No proximity condition'}</h2><p>{review.trigger?`Track 7’s bounding-box bottom reaches the configured image region at ${clock(review.trigger.timestamp)} UTC.`:'The selected track does not meet the configured proximity margin.'}</p><p className="meaning">Proximity does not confirm entry.</p></section>
          <section className="decision">
            {start&&<><p>Check the footage before deciding whether this negative assessment needs follow-up.</p><button className="primary" disabled={busy} onClick={begin}>Review footage <span aria-hidden>→</span></button></>}
            {!start&&!finished&&<><label className="field">Entry annotation<select value={annotation} onChange={e=>setAnnotation(e.target.value)}><option value="not_verified">Not human-verified</option><option value="entry_visible">Entry visible in reviewed footage</option><option value="entry_not_visible">Entry not visible in reviewed footage</option><option value="uncertain">Uncertain</option></select></label><label className="field">Review note<textarea value={note} maxLength={2000} onChange={e=>setNote(e.target.value)} placeholder="Relevant moment and visible action"/></label><label className="ack"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/> I have reviewed the relevant footage</label><button className="primary" disabled={busy||!ack||!review.trigger} onClick={()=>decide('request_xprotect_review')}>Save review request</button><button className="secondary" disabled={busy||!ack} onClick={()=>decide('dismiss')}>Dismiss</button><small>Saves your decision locally. No native event is sent.</small></>}
            {finished&&<><h2>{review.state.status==='dismissed'?'Review dismissed':'Review request saved'}</h2><p>{review.state.status==='dismissed'?'Your decision is saved locally with the original evidence. No native event has been sent.':'Your decision is saved locally with the source camera and observed interval. No native event has been sent.'}</p><button className="secondary" disabled={busy} onClick={()=>{setAck(false);begin();}}>Review footage again</button></>}
          </section>
        </aside>
      </div>
    </main>
    {details&&<EvidenceDetails onClose={()=>setDetails(false)}>
      <h3>Reason for review</h3><p>{review.reason}</p>
      <h3>Original Hafnia response</h3><p>Summary <code>{review.hafnia.summaryId}</code></p><pre>{review.hafnia.originalResponse}</pre><details><summary>Original assessment prompt</summary><p>{(review.hafnia.originalRequest as {Prompt:string}).Prompt}</p></details>
      <h3>Attention region</h3><p>Draw four corners on the footage to change the region. The bounding-box bottom is a proximity proxy.</p><button onClick={()=>{video.current?.pause();setDraft([]);setDrawing(true);setDetails(false);window.scrollTo({top:0});}}>Draw region on footage</button><details><summary>Region coordinates and margin</summary><label className="field">Region polygon<textarea value={polygon} onChange={e=>setPolygon(e.target.value)}/></label><label className="field">Proximity margin (normalized image units)<input type="number" min="0" max="0.1" step="0.005" value={threshold} onChange={e=>setThreshold(Number(e.target.value))}/></label><button disabled={busy} onClick={async()=>{try{const region={polygon:JSON.parse(polygon),threshold};if(await act('configure_region',{region})){setAck(false);setDetails(false);}}catch{setError('Enter a valid polygon as JSON coordinate pairs');}}}>Save attention region</button></details>
      <h3>Track and measured proximity</h3><p>{review.cv.model} · Linux revision <code>{review.cv.revision}</code></p><p>{review.cv.limitation}</p><p>Distance uses normalized image coordinates, with zero inside the polygon; it is not a physical distance.</p><table><thead><tr><th>UTC</th><th>Distance</th><th>Original frame</th></tr></thead><tbody>{review.frames.filter(f=>f.index===0||f.index===review.trigger?.index||f.index===18||f.index===19).map(f=><tr key={f.index}><td>{clock(f.timestamp)}</td><td>{f.distance===null?'No track':f.distance.toFixed(6)}</td><td><a href={f.file} target="_blank" rel="noreferrer">Frame {f.index}</a></td></tr>)}</tbody></table>
      <h3>Human entry annotation</h3><pre>{JSON.stringify(review.state.humanAnnotation??{value:'not_verified'},null,2)}</pre><h3>Separate calibration reference</h3><pre>{JSON.stringify(review.reference,null,2)}</pre>
      <h3>Completed diagnostic context</h3><pre>{JSON.stringify(review.diagnostic,null,2)}</pre>
      <h3>Native XProtect proposal</h3><pre>{JSON.stringify(review.native,null,2)}</pre><a href="/api/review/original" download="original-railway.mkv">Original railway MKV</a>
    </EvidenceDetails>}
  </>;
}

