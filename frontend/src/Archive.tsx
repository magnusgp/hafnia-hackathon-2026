import { useEffect, useState } from 'react';
import { api, ApiError } from './api';
import { cameraLabel, stamp } from './format';
import type { ArchiveEntry } from './types';
import { Chip, Empty, Notice, Spinner } from './ui';

type Listing = { cases: ArchiveEntry[]; unavailable: { id: string; title: string; error: string }[] };

export function Archive({ open }: { open: (id: string) => void }) {
  const [list, setList] = useState<Listing | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.get<Listing>('/api/archive').then(setList).catch((e: ApiError) => setError(e.message)); }, []);
  if (error) return <div className="page"><Notice tone="bad" title="The archive cannot be read">{error}</Notice></div>;
  if (!list) return <div className="page"><Spinner label="Reading the archive…" /></div>;
  const records = list.cases.filter((c) => c.record);
  const experiments = list.cases.filter((c) => !c.record);
  return (
    <div className="page">
      <header className="page-head"><div><h1>Evidence archive</h1>
        <p className="sub">Verified material from before Watches existed. None of it was produced by a Watch configuration, and none of it is an alert Ortru raised.</p></div></header>
      {list.cases.length === 0 && <Empty title="The archive is empty">Prepare the archive with scripts\ortru_prepare.py to bring in the verified historical records.</Empty>}
      {records.length > 0 && <section><h2 className="h2">Authentic records</h2>
        <ul className="cards">{records.map((c) => (
          <li key={c.id}><button className="card" onClick={() => open(c.id)}>
            <b>{c.id.startsWith('live-') ? 'Live assessment started from the browser' : c.title}</b>
            <span>{c.purpose}</span>
            <span className="mono">{stamp(c.interval[0])}</span>
            <Chip tone="good">{c.status}</Chip></button></li>))}</ul></section>}
      {experiments.length > 0 && <section><h2 className="h2">Historical experiments</h2>
        <p className="sub">Single examples run once, kept as evidence. They are not Watches and not product features.</p>
        <ul className="cards">{experiments.map((c) => (
          <li key={c.id}><div className="card static"><b>{c.title}</b><span>{c.purpose}</span><span className="mono">{stamp(c.interval[0])}</span><Chip>{cameraLabel(c.kind === 'video' ? 'video' : 'saved snapshots')}</Chip></div></li>))}</ul></section>}
      {list.unavailable.length > 0 && <Notice tone="review" title="Some records could not be verified">{list.unavailable.map((u) => `${u.title}: ${u.error}`).join(' ')}</Notice>}
    </div>
  );
}
