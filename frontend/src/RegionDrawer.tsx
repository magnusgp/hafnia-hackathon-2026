import { useRef, useState } from 'react';
import type { Region } from './types';

type Pt = [number, number];
const clamp = (v: number) => Math.min(1, Math.max(0, v));

/** Draw the attention region directly on a camera snapshot: click to add points, drag or use arrow keys to adjust. */
export function RegionDrawer({ src, region, onChange, readOnly = false }: { src: string; region: Region | null; onChange?: (r: Region | null) => void; readOnly?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [ratio, setRatio] = useState(16 / 9);
  const [drag, setDrag] = useState<number | null>(null);
  const pts: Pt[] = region?.polygon ?? [];
  const norm = (e: { clientX: number; clientY: number }): Pt => {
    const r = box.current!.getBoundingClientRect();
    return [Math.round(clamp((e.clientX - r.left) / r.width) * 1000) / 1000, Math.round(clamp((e.clientY - r.top) / r.height) * 1000) / 1000];
  };
  const set = (next: Pt[]) => onChange?.(next.length ? { polygon: next } : null);
  const down = (e: React.PointerEvent<HTMLDivElement>) => {
    if (readOnly || drag !== null || pts.length >= 12) return;
    if ((e.target as HTMLElement).closest('.handle')) return;
    set([...pts, norm(e)]);
  };
  const move = (e: React.PointerEvent) => { if (drag !== null) set(pts.map((p, i) => (i === drag ? norm(e) : p))); };
  const key = (i: number, e: React.KeyboardEvent) => {
    const d = e.shiftKey ? 0.05 : 0.01;
    const delta: Record<string, Pt> = { ArrowLeft: [-d, 0], ArrowRight: [d, 0], ArrowUp: [0, -d], ArrowDown: [0, d] };
    if (e.key === 'Backspace' || e.key === 'Delete') { e.preventDefault(); set(pts.filter((_, j) => j !== i)); }
    if (delta[e.key]) { e.preventDefault(); set(pts.map((p, j) => (j === i ? [clamp(p[0] + delta[e.key][0]), clamp(p[1] + delta[e.key][1])] as Pt : p))); }
  };
  return (
    <div className="region-drawer">
      <div className={`snap${readOnly ? '' : ' drawing'}`} ref={box} style={{ aspectRatio: String(ratio) }} onPointerDown={down} onPointerMove={move} onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}>
        <img src={src} alt="Camera snapshot" draggable={false} onLoad={(e) => setRatio(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight || 16 / 9)} />
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
          {pts.length >= 3 ? <polygon className="region" points={pts.map((p) => p.join(',')).join(' ')} /> : pts.length === 2 && <polyline className="region" points={pts.map((p) => p.join(',')).join(' ')} />}
        </svg>
        {!readOnly && pts.map((p, i) => (
          <button key={i} type="button" className="handle" style={{ left: `${p[0] * 100}%`, top: `${p[1] * 100}%` }} aria-label={`Region point ${i + 1}. Arrow keys move it, Delete removes it.`}
            onPointerDown={(e) => { e.stopPropagation(); (e.target as HTMLElement).setPointerCapture(e.pointerId); setDrag(i); }} onKeyDown={(e) => key(i, e)} />
        ))}
      </div>
      {!readOnly && (
        <div className="region-tools">
          <span className="hint">{pts.length < 3 ? `Click the picture to outline the area to watch (${pts.length} of at least 3 points).` : `${pts.length} points. Drag a point to adjust it.`}</span>
          <span className="grow" />
          <button type="button" className="quiet small" disabled={!pts.length} onClick={() => set(pts.slice(0, -1))}>Undo point</button>
          <button type="button" className="quiet small" disabled={!pts.length} onClick={() => set([])}>Clear</button>
        </div>
      )}
    </div>
  );
}
