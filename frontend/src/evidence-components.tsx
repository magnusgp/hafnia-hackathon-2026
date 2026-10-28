import {useEffect, useRef, useState} from 'react';

export const reviewLabels:Record<string,string> = {review_required:'Awaiting review',reviewing:'Review in progress',dismissed:'Dismissed',review_request_saved:'Review request saved locally',xprotect_review_requested:'Review request saved locally'};
export const clock = (utc:string) => utc.slice(11,23);
export function SourceInterval({camera,interval}:{camera:string;interval:string[]}){
  return <p className="camera">{camera}<span> · {interval[0].slice(0,10)} · {clock(interval[0]).slice(0,8)}–{clock(interval[1]).slice(0,8)} UTC</span></p>;
}
export function ReviewState({status}:{status:string}){
  return <div className={'state '+(['dismissed','review_request_saved','xprotect_review_requested'].includes(status)?'resolved':'')} role="status"><span/>{reviewLabels[status]??status}</div>;
}
export function EvidenceDetails({children,onClose}:{children:React.ReactNode;onClose:()=>void}){
  const close=useRef(onClose);close.current=onClose;
  useEffect(()=>{
    const previous=document.body.style.overflow;document.body.style.overflow='hidden';
    const key=(e:KeyboardEvent)=>{
      if(e.key==='Escape')close.current();
      if(e.key==='Tab'){
        const all=Array.from(document.querySelectorAll<HTMLElement>('.details button:not(:disabled),.details a,.details input,.details select,.details textarea,.details summary')).filter(el=>el.getClientRects().length>0);
        const first=all[0],last=all[all.length-1];
        if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
        if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
      }
    };
    document.addEventListener('keydown',key);
    return()=>{document.body.style.overflow=previous;document.removeEventListener('keydown',key);document.querySelector<HTMLButtonElement>('[data-details]')?.focus();};
  },[]);
  return <div className="scrim" onClick={onClose}><section className="details" role="dialog" aria-modal="true" aria-label="Evidence details" onClick={e=>e.stopPropagation()}><div className="details-title"><h2>Evidence details</h2><button autoFocus onClick={onClose}>Close</button></div>{children}</section></div>;
}
export type Sample = {index:number;timestamp:string;file:string;box:number[]|null};
export function SnapshotEvidence({frames,polygon,subject,onError}:{frames:Sample[];polygon:number[][]|null;subject:string;onError:()=>void}){
  const [index,setIndex]=useState(0),[overlay,setOverlay]=useState(true),[loaded,setLoaded]=useState(-1);
  const current=frames[index], box=current.box;
  return <section className="footage" aria-label="Recorded snapshots">
    <div className="snapshot-stage">
      <img key={current.file} src={current.file} alt={`${subject} original recorded sample at ${current.timestamp}`} onLoad={()=>setLoaded(index)} onError={onError}/>
      {overlay&&loaded===index&&polygon&&<svg className="track-overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-label={`${subject} CV localization`}>
        <polygon points={polygon.map(p=>p.join(',')).join(' ')} fill="rgba(40,88,214,.08)" stroke="#8cb3ff" strokeWidth=".002" strokeDasharray=".008 .006"/>
        {box&&<rect data-object={subject} data-frame={index} x={box[0]} y={box[1]} width={box[2]-box[0]} height={box[3]-box[1]} fill="none" stroke="#FFD185" strokeWidth=".003"/>}
      </svg>}
    </div>
    <div className="media-caption"><span><span className="record-dot"/> Original timestamped snapshots · no saved original video</span><time>{clock(current.timestamp)} UTC</time></div>
    <div className="sample-controls"><button disabled={index===0} onClick={()=>setIndex(i=>i-1)}>Previous sample</button><label>Recorded sample {index+1} of {frames.length}<input aria-label="Recorded sample" type="range" min="0" max={frames.length-1} value={index} onChange={e=>setIndex(Number(e.target.value))}/></label><button disabled={index===frames.length-1} onClick={()=>setIndex(i=>i+1)}>Next sample</button></div>
    <div className="track-caption"><div><strong>{polygon?`${subject} foreground hypothesis`:'Visual evidence only'}</strong><span>{polygon?'Box localization and draft walkway region; physical clearance is not measured.':'No local CV results are available for this recording.'}</span></div>{polygon&&<label><input type="checkbox" checked={overlay} onChange={e=>setOverlay(e.target.checked)}/> Show CV overlay</label>}</div>
  </section>;
}
export function ReviewControls({status,busy,saved,act}:{status:string;busy:boolean;saved:null|{value:string;note:string};act:(action:string,body:object)=>Promise<boolean>}){
  const [ack,setAck]=useState(false),[annotation,setAnnotation]=useState('not_verified'),[note,setNote]=useState('');
  const finished=['dismissed','review_request_saved'].includes(status);
  return <section className="decision">
    {status==='review_required'&&<><p>Inspect the recorded samples and both evidence sources before deciding.</p><button className="primary" disabled={busy} onClick={()=>act('review',{})}>Review footage <span aria-hidden>→</span></button></>}
    {status==='reviewing'&&<><label className="field">Visible condition annotation<select value={annotation} onChange={e=>setAnnotation(e.target.value)}><option value="not_verified">Not human-verified</option><option value="condition_visible">Condition visible in reviewed footage</option><option value="condition_not_visible">Condition not visible in reviewed footage</option><option value="uncertain">Uncertain</option></select></label><label className="field">Review note<textarea value={note} maxLength={2000} onChange={e=>setNote(e.target.value)} placeholder="Relevant timestamp and visible condition"/></label><label className="ack"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/> I have reviewed the relevant footage</label><button className="primary" disabled={busy||!ack} onClick={()=>act('save_review_request',{annotation,note,footageReviewed:ack})}>Save review request</button><button className="secondary" disabled={busy||!ack} onClick={()=>act('dismiss',{annotation,note,footageReviewed:ack})}>Dismiss</button></>}
    {finished&&<><h2>{status==='dismissed'?'Review dismissed':'Review request saved'}</h2><p>Your decision is saved locally for this case. No native event has been sent.</p>{saved&&<p className="saved-note">{saved.note||'No review note supplied.'}</p>}<button className="secondary" disabled={busy} onClick={()=>{setAck(false);setAnnotation(saved?.value??'not_verified');setNote(saved?.note??'');act('review',{});}}>Review footage again</button></>}
    <small>Local review record. No native XProtect alarm is created.</small>
  </section>;
}
