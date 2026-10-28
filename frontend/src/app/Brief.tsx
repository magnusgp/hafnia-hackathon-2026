import type {Case} from './types';
import {clock, ms, seconds} from './format';

const NATIVE: Record<string, [string, string]> = {
  not_configured: ['Not set up', 'The review alarm has not been created in XProtect.'],
  configured: ['Ready', 'Nothing has been sent yet.'],
  sent: ['Sent', 'The Event Server accepted it. Not yet confirmed in Smart Client.'],
  alarm_verified: ['In Smart Client', 'The alarm was confirmed in the Alarm Manager.'],
  blocked: ['Blocked', 'The handoff could not complete.'],
};

export function Brief({c, seek, onAct, onDetails}: {c: Case; seek: (t: number) => void; onAct: (a: 'request' | 'dismiss') => void; onDetails: () => void}) {
  const saved = ['xprotect_review_requested', 'review_request_saved'].includes(c.state.status);
  const dismissed = c.state.status === 'dismissed';
  const open = !saved && !dismissed;
  const trigger = c.vision?.trigger ?? null;
  const decisive = c.agent?.decisiveMoment ?? null;
  const lead = trigger && decisive ? (ms(decisive.timestamp) - ms(trigger.timestamp)) / 1000 : null;
  const entry = c.agent?.decision === 'entry_visible' && c.agent.currentSource;
  const [nativeLabel, nativeNote] = NATIVE[c.native.state] ?? [c.native.state, ''];
  return (
    <aside className="brief" aria-label="Second signal and XProtect handoff">
      <header className="brief-head">
        <p className={`status ${open ? 'open' : 'done'}`}>{c.flagship ? (saved ? 'Review requested' : dismissed ? 'Not needed' : 'Ready for XProtect review') : 'Saved evidence'}</p>
        <h1>{c.flagship ? 'Review the station platform' : c.title}</h1>
        {!c.flagship && <p className="lede">{c.purpose}</p>}
      </header>

      <ol className="signals">
        <Signal who="Hafnia" head={c.hafnia.answer ?? answerHead(c)} note={snippet(c.hafnia.quote)} />
        {c.flagship && trigger && trigger.mediaTime !== null && (
          <Signal who="Local vision" head="Person at the platform edge" at={clock(trigger.timestamp, 1)}
            note={lead ? `Flagged ${seconds(lead)} before the person climbs down.` : 'A person was inside the watched region.'} onClick={() => seek(trigger.mediaTime!)} tone="vision" />
        )}
        {!c.flagship && c.vision && <Signal who="Local vision" head={visionHead(c)} note={c.vision.meaning} tone="vision" />}
        {c.agent && decisive && (
          <Signal who="Footage review" head={entry ? 'Person reaches the track bed' : 'Reviewed'} at={clock(decisive.timestamp, 1)}
            note={`${c.agent.reviewer}, an AI reviewer. Not a human review.`} onClick={() => seek(decisive.mediaTime)} tone="review" />
        )}
      </ol>

      {c.handoff ? (
        <section className="handoff" aria-label="What XProtect receives">
          <h2>What XProtect receives</h2>
          <dl>
            <div><dt>Camera</dt><dd>{c.handoff.camera}</dd></div>
            <div><dt>Recording</dt><dd className="mono">{clock(c.handoff.window[0])}–{clock(c.handoff.window[1])} UTC</dd></div>
          </dl>
          <p className="message">{c.handoff.message}</p>
          {open && <button className="primary wide" onClick={() => onAct('request')}>Send to XProtect review</button>}
          {open && <button className="link" onClick={() => onAct('dismiss')}>Not needed</button>}
          {saved && <p className="saved">Your review request is saved{c.state.humanAnnotation ? `: ${c.state.humanAnnotation.value.replace(/_/g, ' ')}` : ''}.</p>}
          <p className={`native ${c.native.state}`}><b>{nativeLabel}</b> {nativeNote}{c.native.alarmId ? ` Alarm ${c.native.alarmId}.` : ''}</p>
        </section>
      ) : (
        <section className="handoff plain">
          <p className="native"><b>Evidence only</b> No XProtect alarm is defined for this camera.</p>
          {open && <button className="primary wide" onClick={() => onAct('request')}>Save for review</button>}
          {open && <button className="link" onClick={() => onAct('dismiss')}>Not needed</button>}
          {!open && <p className="saved">Decision saved on this computer.</p>}
        </section>
      )}
      <button className="link details" onClick={onDetails}>Evidence details</button>
    </aside>
  );
}

function Signal({who, head, note, at, tone, onClick}: {who: string; head: string; note: string; at?: string; tone?: string; onClick?: () => void}) {
  const inner = <><span className="who">{who}{at && <time>{at}</time>}</span><strong>{head}</strong><span className="note">{note}</span></>;
  return <li className={tone}>{onClick ? <button onClick={onClick}>{inner}</button> : <div>{inner}</div>}</li>;
}
const snippet = (s: string) => s.replace(/```json|```/g, '').trim().split(/[,;.]/)[0];
const answerHead = (c: Case) => c.hafnia.answers && c.hafnia.answers.length > 1 ? 'Two prompts, two readings' : 'Answered';
const visionHead = (c: Case) => c.vision?.runs?.length ? `Still for ${c.vision.runs[0].sampled_span_s.toFixed(1)} s across ${c.vision.runs[0].samples} samples` : 'Measured';
export const annotationLabel = (v: string) => ({entry_visible: 'Entry visible', condition_visible: 'Condition visible', entry_not_visible: 'Entry not visible', condition_not_visible: 'Condition not visible', uncertain: 'Unsure', not_verified: 'No visual verdict'} as Record<string, string>)[v] ?? v;
