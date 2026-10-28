let csrf = '';
export async function api<T = any>(path: string, body?: object): Promise<T> {
  const r = await fetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Review-CSRF': csrf}, body: JSON.stringify(body)} : undefined);
  let result: any = {};
  try { result = await r.json(); } catch { /* non-JSON error body */ }
  if (result.csrf) csrf = result.csrf;
  if (!r.ok) throw Object.assign(new Error(result.error ?? 'Request failed'), {status: r.status});
  return result;
}
