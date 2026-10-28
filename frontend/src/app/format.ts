export const ms = (ts: string) => Date.parse(ts);
export function clock(ts: string, digits = 0) {
  const d = new Date(ts); const p = (n: number, w = 2) => String(n).padStart(w, '0');
  const base = `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`;
  return digits ? `${base}.${p(d.getUTCMilliseconds(), 3).slice(0, digits)}` : base;
}
export function day(ts: string) {
  return new Date(ts).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'});
}
/** Stream time of a UTC instant: sample i sits at max(0, i*0.5 - 0.1) seconds in the browser video. */
export const mediaOf = (ts: string, origin: string) => Math.max(0, (ms(ts) - ms(origin)) / 1000 - 0.1);
export const utcAt = (t: number, origin: string) => new Date(ms(origin) + (t + 0.1) * 1000).toISOString();
export const seconds = (n: number) => `${n.toFixed(1)} s`;
