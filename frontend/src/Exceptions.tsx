import { useEffect } from 'react';
import { cameraLabel, day, hms, DECISION_LABEL } from './format';
import { Investigation } from './Investigation';
import type { Bootstrap, Queue, QueueItem } from './types';
import { Chip, Empty, Notice, Spinner } from './ui';

function status(i: QueueItem): { label: string; tone: 'plain' | 'good' | 'review' | 'bad' } {
  if (i.broken) return { label: 'Cannot verify', tone: 'bad' };
  if (i.smartClient === 'verified') return { label: 'Alarm verified', tone: 'good' };
  if (i.native === 'sent') return { label: 'Sent to XProtect', tone: 'good' };
  if (i.native === 'uncertain') return { label: 'Send uncertain', tone: 'bad' };
  if (i.decision === 'review_requested') return { label: 'Review requested', tone: 'review' };
  if (i.decision && i.decision !== 'undecided') return { label: DECISION_LABEL[i.decision] ?? i.decision, tone: 'plain' };
  return { label: 'Needs review', tone: 'review' };
}

function Row({ item, on, go }: { item: QueueItem; on: boolean; go: (i: QueueItem) => void }) {
  const s = status(item);
  return (
    <li>
      <button className={`qrow${on ? ' on' : ''}`} onClick={() => go(item)} aria-current={on ? 'true' : undefined}>
        <span className="qtop"><b>{item.title ?? (item.camera ? cameraLabel(item.camera.name) : 'Unavailable')}</b><Chip tone={s.tone}>{s.label}</Chip></span>
        <span className="qwhy">{item.policy?.label ?? item.reason}</span>
        <span className="qmeta mono">{item.at ? `${day(item.at)} ${hms(item.at).slice(0, 8)}` : ''}{item.watch ? ` · ${item.watch.name}` : ''}</span>
      </button>
    </li>
  );
}

export function Exceptions({ queue, boot, selected, select, refresh }: {
  queue: Queue | null; boot: Bootstrap; selected: { id: string; origin: 'live' | 'archive' } | null;
  select: (s: { id: string; origin: 'live' | 'archive' } | null) => void; refresh: () => void;
}) {
  useEffect(() => {
    if (queue && !selected) {
      const first = queue.live[0] ?? queue.records[0];
      if (first && !first.broken) select({ id: first.id, origin: first.origin });
    }
  }, [queue, selected, select]);
  if (!queue) return <div className="workspace"><Spinner label="Loading exceptions…" /></div>;
  const go = (i: QueueItem) => { if (!i.broken) select({ id: i.id, origin: i.origin }); };
  const active = boot.watches.filter((w) => w.status === 'active').length;
  const waiting = boot.watches.flatMap((w) => w.jobs).filter((j) => j.stages.some((s) => s.status === 'needs_you'));
  return (
    <div className="workspace">
      <aside className="queue" aria-label="Exception queue">
        <div className="qhead"><h2>Exceptions</h2><span className="mono">{queue.live.filter((i) => (i.decision ?? 'undecided') === 'undecided').length} open</span></div>
        {waiting.length > 0 && <div className="qnote"><Notice tone="review" title="Hafnia is waiting">{waiting.length} recorded window{waiting.length > 1 ? 's' : ''} read and checked by local vision; the Hafnia step needs a gateway sign-in.</Notice></div>}
        <ul>{queue.live.map((i) => <Row key={i.id} item={i} on={selected?.id === i.id} go={go} />)}</ul>
        {queue.live.length === 0 && (
          <div className="qempty">
            <p><b>No exceptions from Watches yet.</b></p>
            <p>{active ? 'Active Watches raise an exception when their policy is met by a real assessment.' : 'Create a Watch and activate it. Ortru reads recorded windows of that camera and raises an exception when Hafnia and local vision call for a look.'}</p>
            <a className="primary-link" href="#/watches">{boot.watches.length ? 'Open Watches' : 'Create a Watch'}</a>
          </div>
        )}
        {queue.records.length > 0 && <><div className="qgroup">Earlier verified records</div>
          <ul>{queue.records.map((i) => <Row key={i.id} item={i} on={selected?.id === i.id} go={go} />)}</ul></>}
      </aside>
      <main className="detail">
        {selected ? <Investigation id={selected.id} origin={selected.origin} onChanged={refresh} />
          : <Empty title="Nothing to review right now" action={<a className="primary-link" href="#/watches">Open Watches</a>}>Exceptions appear here when a Watch’s assessment meets its attention policy.</Empty>}
      </main>
    </div>
  );
}
