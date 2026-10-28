export type Frame = {index: number; timestamp: string; mediaTime: number | null; box: number[] | null; near: boolean; distance?: number; file: string};
export type Agent = null | {
  reviewer: string; provenance: string; decision: string; headline: string; basis: string; limits: string; currentSource: boolean;
  decisiveMoment: {timestamp: string; mediaTime: number; what: string};
  phases: {start: string; end: string; kind: 'edge' | 'tracks'; label: string}[];
  observations: {timestamp: string; sample: number | null; what: string}[];
};
export type Human = null | {value: string; note: string; at: string; provenance: string};
export type CaseState = {status: string; version: number; humanAnnotation: Human; reviewed: boolean; region?: {polygon: number[][]; threshold: number}};
export type Native = {eventName: string; state: string; alarmId: string | null; detail: string; sentAt?: string; canSend?: boolean};
export type Answer = {summaryId: string; quote: string; parsed: string; prompt: string};
export type Vision = null | {
  label: string; model: string; meaning: string; trackId?: number; region: null | {polygon: number[][]; threshold: number} | number[][];
  trigger?: Frame | null; regionStatus?: string; runs?: {first: string; last: string; sampled_span_s: number; samples: number}[];
};
export type Case = {
  id: string; flagship: boolean; title: string; camera: string; interval: string[]; purpose: string; revision: string; actionRevision: string;
  kind: 'video' | 'snapshots'; frames: Frame[];
  video: null | {url: string; duration: number; fps: number; origin: string; sha256: string};
  hafnia: {answer?: string; verdict?: string; quote: string; summaryId?: string; request?: string; answers?: Answer[]};
  handoff?: {event: string; camera: string; window: string[]; message: string; alarm: string};
  vision: Vision; agent: Agent; state: CaseState; native: Native; limitations: string[];
  diagnostic?: any; provenance?: any;
};
export type Summary = {id: string; flagship: boolean; title: string; purpose: string; interval: string[]; kind: string; status: string};
export type Stage = {key: string; label: string; status: 'waiting' | 'running' | 'done' | 'failed' | 'needs_you'; detail?: string};
export type Job = {id: string; state: string; stages: Stage[]; error?: {reason: string; next: string} | null; caseId?: string | null; camera: string; interval: string[]};
export type Assessment = null | {available: boolean; reason?: string; next?: string; cameras: {id: string; name: string; title: string}[]; defaults?: {start: string; end: string}};
