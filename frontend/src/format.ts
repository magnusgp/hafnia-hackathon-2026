const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const p2 = (n: number) => String(n).padStart(2, '0');

/** HH:MM:SS.s in UTC with one decimal, the same notation the evidence uses. */
export function hms(iso: string): string {
  const d = new Date(iso);
  return `${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}:${p2(d.getUTCSeconds())}.${Math.floor(d.getUTCMilliseconds() / 100)}`;
}
export function day(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}
export function stamp(iso: string): string { return `${day(iso)} ${hms(iso).slice(0, 8)} UTC`; }
export function clock(seconds: number): string {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${p2(Math.floor(s % 60))}.${Math.floor((s * 10) % 10)}`;
}
export function ago(iso: string, now = Date.now()): string {
  const s = Math.round((now - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
export function until(iso: string | null, now = Date.now()): string {
  if (!iso) return 'not scheduled';
  const s = Math.round((new Date(iso).getTime() - now) / 1000);
  if (s <= 30) return 'due now';
  if (s < 3600) return `in ${Math.round(s / 60)} min`;
  return `in ${Math.round(s / 3600)} h`;
}
export function cameraLabel(name: string): string {
  return name.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}
export const DECISION_LABEL: Record<string, string> = {
  undecided: 'Needs review', review_requested: 'Review requested', dismissed: 'Dismissed', confirmed: 'Confirmed',
};
export const VERDICT_LABEL: Record<string, string> = { visible: 'Yes', not_visible: 'No', unclear: "Can't tell", entry_visible: 'Yes', entry_not_visible: 'No', not_verified: 'Not verified' };
