import { StrictMode, useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/700.css';
import '@fontsource/space-grotesk/600.css';
import '@fontsource/ibm-plex-mono/400.css';
import './style.css';
import { api, ApiError } from './api';
import { Archive } from './Archive';
import { Exceptions } from './Exceptions';
import type { Bootstrap, Queue } from './types';
import { Chip, Mark, Notice, Spinner } from './ui';
import { WatchEditor } from './WatchEditor';
import { WatchList, WatchPage } from './Watches';

type Route = { page: 'exceptions' } | { page: 'watches'; id?: string; edit?: boolean; create?: boolean } | { page: 'archive'; id?: string };
function parse(hash: string): Route {
  const p = hash.replace(/^#\/?/, '').split('/');
  if (p[0] === 'watches') return p[1] === 'new' ? { page: 'watches', create: true } : p[1] ? { page: 'watches', id: p[1], edit: p[2] === 'edit' } : { page: 'watches' };
  if (p[0] === 'archive') return { page: 'archive', id: p[1] };
  return { page: 'exceptions' };
}

function App() {
  const [route, setRoute] = useState<Route>(() => parse(location.hash));
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [selected, setSelected] = useState<{ id: string; origin: 'live' | 'archive' } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [b, q] = await Promise.all([api.get<Bootstrap>('/api/ortru'), api.get<Queue>('/api/queue')]);
      setBoot(b); setQueue(q); setError(null);
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Ortru could not load.'); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { const h = () => setRoute(parse(location.hash)); window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, []);
  // While any assessment is running, follow its progress.
  const running = boot?.watches.some((w) => w.jobs.some((j) => !['completed', 'failed'].includes(j.state) && !j.stages.some((s) => s.status === 'needs_you')));
  useEffect(() => { if (!running) return; const t = setInterval(() => void refresh(), 3000); return () => clearInterval(t); }, [running, refresh]);
  const go = (h: string) => { location.hash = h; };

  const open = queue ? queue.live.filter((i) => (i.decision ?? 'undecided') === 'undecided').length : 0;
  const nav = (page: string, label: string, extra?: string) => <a href={`#/${page === 'exceptions' ? '' : page}`} className={route.page === page ? 'on' : ''} aria-current={route.page === page ? 'page' : undefined}>{label}{extra && <span className="count">{extra}</span>}</a>;

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <a className="brand" href="#/" aria-label="Ortru, exceptions"><Mark size={30} /><span>Ortru</span></a>
        <nav aria-label="Primary">{nav('exceptions', 'Exceptions', open ? String(open) : undefined)}{nav('watches', 'Watches', boot?.watches.length ? String(boot.watches.length) : undefined)}{nav('archive', 'Evidence archive')}</nav>
        {boot && <div className="status">
          <Chip tone={boot.gateway.available ? 'good' : 'review'} title={boot.gateway.reason ?? 'Hafnia gateway session is active in the server.'}>{boot.gateway.available ? 'Hafnia connected' : 'Hafnia: sign-in needed'}</Chip>
          <Chip tone={boot.native.sending ? 'good' : 'plain'} title={`Event Server ${boot.native.target}`}>{boot.native.sending ? 'XProtect sending on' : 'XProtect sending off'}</Chip>
        </div>}
      </header>
      <div id="main" tabIndex={-1}>
        {error && <div className="page"><Notice tone="bad" title="Ortru cannot load" action={<button className="quiet" onClick={refresh}>Try again</button>}>{error}</Notice></div>}
        {!error && !boot && <div className="page"><Spinner label="Starting Ortru…" /></div>}
        {boot && route.page === 'exceptions' && <Exceptions queue={queue} boot={boot} selected={selected} select={setSelected} refresh={refresh} />}
        {boot && route.page === 'watches' && (route.create
          ? <WatchEditor boot={boot} watch={null} refresh={refresh} cancel={() => go('/watches')} done={(id) => go(`/watches/${id}`)} />
          : route.id ? (() => {
            const w = boot.watches.find((x) => x.id === route.id);
            if (!w) return <div className="page"><Notice tone="bad" title="This Watch does not exist" action={<a className="primary-link" href="#/watches">All Watches</a>} /></div>;
            return route.edit ? <WatchEditor key={`${w.id}-${w.version}`} boot={boot} watch={w} refresh={refresh} cancel={() => go(`/watches/${w.id}`)} done={(id) => go(`/watches/${id}`)} />
              : <WatchPage boot={boot} watch={w} refresh={refresh} back={() => go('/watches')} edit={() => go(`/watches/${w.id}/edit`)} openException={(id) => { setSelected({ id, origin: 'live' }); go('/'); }} />;
          })() : <WatchList boot={boot} open={(id) => go(`/watches/${id}`)} create={() => go('/watches/new')} />)}
        {boot && route.page === 'archive' && (<Archive open={(id) => { setSelected({ id, origin: 'archive' }); go('/'); }} />)}
      </div>
    </>
  );
}



createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
