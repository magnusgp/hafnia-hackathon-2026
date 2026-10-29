// Shapes of the ortru.v1 API. Every response is an Envelope; every action returns the normalized object it changed.
export type Envelope<T> = { schema: 'ortru.v1'; ok: boolean; data: T | null; error: { message: string; code?: string } | null; csrf?: string };

export type Region = { polygon: [number, number][] };
export type Capability = {
  id: string; label: string; available: boolean; reason?: string; needsRegion: boolean; model?: string;
  parameters: Record<string, { type: string; default: number; min: number; max: number; label: string }>;
  establishes: string; cannot: string;
};
export type Camera = { id: string; name: string; hasSnapshot: boolean; native: string | null };
export type PolicyKind = { id: string; label: string };

export type WatchConfig = {
  name: string;
  camera: { id: string; name: string };
  hafnia: { instruction: string; condition: string; prompt: string; output: { keys: string[]; outcomes: string[] } };
  detector: { id: string; parameters: Record<string, number> };
  region: Region;
  policy: { raiseOn: string[] };
  schedule: { intervalMinutes: number; windowSeconds: number; marginSeconds: number };
  quota: { perDay: number };
  native: { event: string; alarm: string | null };
};
export type Stage = { key: string; label: string; status: 'done' | 'running' | 'waiting' | 'failed' | 'needs_you'; detail?: string };
export type Job = {
  id: string; watchId: string; version: number; state: string; trigger: string; interval: [string, string]; stages: Stage[];
  error: { reason: string; next: string } | null; resumable: boolean; created: string; exceptionId: string | null;
};
export type Schedule = {
  status: string; intervalMinutes: number; nextDue: string | null; runningJob: string | null;
  lastAssessment: { id: string; at: string } | null; lastJob: { id: string; state: string; at: string } | null;
  lastCheck: { at: string; text: string } | null; usedToday: number; budgetPerDay: number; globalUsedToday: number; globalBudget: number;
};
export type Watch = {
  id: string; status: 'draft' | 'active' | 'paused' | 'disabled'; version: number; updated: string; config: WatchConfig;
  problems: { code: string; blocking: boolean; text: string }[]; schedule: Schedule; jobs: Job[]; history: { at: string; text: string }[]; hasSnapshot: boolean;
};
export type Bootstrap = {
  capabilities: Capability[]; policyKinds: PolicyKind[]; cameras: Camera[]; watches: Watch[];
  gateway: { available: boolean; reason: string | null }; native: { sending: boolean; target: string }; budget: { global_: number; usedToday: number };
};

export type Sample = { index: number; timestamp: string; mediaTime: number | null; box: number[] | null; distance: number | null; near: boolean };
export type NativeState = {
  state: 'ready' | 'sent' | 'blocked' | 'uncertain' | 'not_configured' | 'no_event' | 'not_sent';
  detail?: string; destination?: { event: string; alarm: string; target: string; camera: string } | null;
  transport?: { state: string | null; attempt?: number; at?: string | null; httpStatus?: number | null } | null;
  smartClient?: 'verified' | 'not_verified'; alarm?: string | null;
};
export type Decision = { revision: number; status: string; verdict: string | null; note: string; outcome?: string | null; at: string | null; readOnly?: boolean };
export type Outcome = { id: string; label: string; enabled?: boolean; why?: string | null };
export type Investigation = {
  schema: 'ortru.v1'; id: string; kind: 'live' | 'archive'; origin?: string; note?: string; title?: string; record?: boolean;
  raised: boolean; revision?: string; watch: { id: string; version: number; name: string } | null; camera: { id?: string; name: string };
  interval: [string, string]; at: string; reason: string;
  policy: { kind: string; raised: boolean; label: string; raiseOn?: string[] };
  hafnia: { answer: string | null; outcome?: string; tone: string | null; quote: string | null; timing?: string | null; limitations?: string | null; summaryId?: string | null; prompt?: string | null; source: string };
  vision: null | {
    detector: string | null; parameters?: Record<string, number>; device?: string | null; model?: string | null; region?: Region | null; samples: Sample[];
    trackId: number | null; trigger: Sample | null; samplesPerSecond?: number | null; meaning?: string | null;
  };
  video: null | { url: string; duration: number; fps: number; origin: string; sha256: string };
  frames: { index: number; url: string }[];
  review?: { question: string; options: { id: string; label: string }[]; condition: string; outcomes: Outcome[] };
  handoff: null | { event: string; alarm: string | null; camera: string; window: [string, string]; message: string };
  decision: Decision; native: NativeState;
  provenance: { hashes: { name: string; path?: string; sha256: string }[]; watchConfig?: WatchConfig; hafniaRequestSha256?: string; continuity?: string; human?: string; reference?: unknown };
  limitations: string[] | null;
};
export type QueueItem = {
  id: string; origin: 'live' | 'archive'; camera?: { name: string }; at?: string; interval?: [string, string]; reason: string; watch?: { id: string; version: number; name: string } | null;
  policy?: { kind: string; label: string }; hafniaTone?: string | null; hafniaAnswer?: string | null; decision?: string; native?: string | null; smartClient?: string | null;
  title?: string | null; broken?: boolean;
};
export type Queue = { live: QueueItem[]; records: QueueItem[] };
export type NativePreview = { dispatchKey: string; sha256: string; xml: string; destination: string; camera: string; event: string; alarm: string | null; enabled: boolean; previous: { attempt: number; state: string; at: string }[]; consequence: string };
export type ArchiveEntry = { id: string; title: string; purpose: string; interval: [string, string]; kind: string; status: string; record: boolean; note: string };
