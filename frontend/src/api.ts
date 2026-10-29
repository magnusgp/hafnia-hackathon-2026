import type { Envelope } from './types';

let csrf = '';

export class ApiError extends Error {
  code?: string; status: number;
  constructor(message: string, status: number, code?: string) { super(message); this.status = status; this.code = code; }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method, credentials: 'same-origin',
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), 'X-Ortru-CSRF': csrf },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('Ortru cannot reach its server. Check that it is running, then try again.', 0);
  }
  let env: Envelope<T> | null = null;
  try { env = await res.json(); } catch { /* not JSON */ }
  if (env?.csrf) csrf = env.csrf;
  if (!env || !env.ok || env.data === null) throw new ApiError(env?.error?.message ?? `The server answered ${res.status}.`, res.status, env?.error?.code);
  return env.data;
}

export const api = {
  get: <T,>(path: string) => call<T>('GET', path),
  post: <T,>(path: string, body: unknown = {}) => call<T>('POST', path, body),
  put: <T,>(path: string, body: unknown) => call<T>('PUT', path, body),
};
