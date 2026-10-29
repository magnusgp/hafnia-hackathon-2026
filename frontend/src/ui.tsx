import { useEffect, useRef, type ReactNode } from 'react';
import markUrl from '../../brand-kit/ortru/mark.svg';

export function Mark({ size = 28 }: { size?: number }) {
  return <img src={markUrl} width={size} height={size} alt="" aria-hidden="true" className="mark" />;
}

export function Chip({ tone = 'plain', children, title }: { tone?: 'plain' | 'hafnia' | 'vision' | 'good' | 'review' | 'bad'; children: ReactNode; title?: string }) {
  return <span className={`chip ${tone}`} title={title}>{children}</span>;
}

export function Source({ who }: { who: 'hafnia' | 'vision' }) {
  return <span className={`source ${who}`}><i aria-hidden="true" />{who === 'hafnia' ? 'Hafnia' : 'Local vision'}</span>;
}

export function Spinner({ label }: { label: string }) {
  return <div className="loading" role="status"><span className="spin" aria-hidden="true" />{label}</div>;
}

export function Notice({ tone = 'plain', title, children, action }: { tone?: 'plain' | 'review' | 'bad' | 'good'; title?: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={`notice ${tone}`} role={tone === 'bad' ? 'alert' : 'status'}>
      <div>{title && <b>{title}</b>}{children && <p>{children}</p>}</div>
      {action}
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty"><Mark size={44} /><h2>{title}</h2>{children && <p>{children}</p>}{action}</div>;
}

/** Modal dialog with focus handling: Escape closes, focus returns to the opener. */
export function Dialog({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', key);
    return () => { window.removeEventListener('keydown', key); opener?.focus?.(); };
  }, [onClose]);
  return (
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`dialog${wide ? ' wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <header><h2>{title}</h2><button className="icon" onClick={onClose} aria-label="Close">×</button></header>
        {children}
      </div>
    </div>
  );
}
