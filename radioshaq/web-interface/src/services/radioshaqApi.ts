import type { AudioConfig, PendingResponse } from '../types/audio';

const API_BASE = import.meta.env.VITE_RADIOSHAQ_API ?? 'http://localhost:8000';

/** API base URL for status display. */
export function getApiBase(): string {
  return API_BASE;
}

/** Optional: set token at runtime (e.g. after login) so API calls use it. */
let runtimeToken: string | null = null;
export function setApiToken(token: string | null) {
  runtimeToken = token;
}
function authHeaders(): HeadersInit {
  const token = runtimeToken ?? import.meta.env.VITE_RADIOSHAQ_TOKEN;
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  return headers;
}

// ----- Auth -----
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export async function getToken(params: { subject: string; role?: string; station_id?: string }): Promise<TokenResponse> {
  const search = new URLSearchParams({ subject: params.subject });
  if (params.role) search.set('role', params.role);
  if (params.station_id) search.set('station_id', params.station_id);
  const res = await fetch(`${API_BASE}/auth/token?${search}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to get token');
  return res.json();
}

export interface MeResponse {
  sub: string;
  role: string;
  station_id?: string;
  scopes?: string[];
}
export async function getMe(): Promise<MeResponse> {
  const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to get current user');
  return res.json();
}

// ----- Health -----
export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}
export async function getHealthReady(): Promise<{ status: string; checks?: Record<string, string> }> {
  const res = await fetch(`${API_BASE}/health/ready`);
  if (!res.ok) throw new Error('Ready check failed');
  return res.json();
}

// ----- Audio (existing) -----
export async function getAudioConfig(): Promise<AudioConfig> {
  const res = await fetch(`${API_BASE}/api/v1/config/audio`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch config');
  return res.json();
}

export async function updateAudioConfig(config: Partial<AudioConfig>): Promise<AudioConfig> {
  const res = await fetch(`${API_BASE}/api/v1/config/audio`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to update config');
  return res.json();
}

export async function listAudioDevices(): Promise<{ input_devices: { index: number; name: string }[]; output_devices: { index: number; name: string }[] }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/devices`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch devices');
  return res.json();
}

export async function listPendingResponses(): Promise<{ pending_responses: PendingResponse[]; count: number }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/pending`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch pending');
  return res.json();
}

export async function approvePendingResponse(pendingId: string, operator?: string): Promise<{ pending: PendingResponse }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/pending/${pendingId}/approve`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ operator }),
  });
  if (!res.ok) throw new Error('Failed to approve');
  return res.json();
}

export async function rejectPendingResponse(pendingId: string, operator?: string, notes?: string): Promise<{ pending: PendingResponse }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/pending/${pendingId}/reject`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ operator, notes }),
  });
  if (!res.ok) throw new Error('Failed to reject');
  return res.json();
}

export function connectMetricsWebSocket(sessionId: string): WebSocket {
  let wsUrl: string;
  try {
    const url = new URL(API_BASE);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = `/ws/audio/metrics/${sessionId}`;
    wsUrl = url.toString();
  } catch {
    const protocol = API_BASE.startsWith('https') ? 'wss:' : 'ws:';
    const afterProto = API_BASE.replace(/^https?:\/\//, '');
    const origin = `${protocol}//${afterProto.split('/')[0]}`;
    wsUrl = `${origin}/ws/audio/metrics/${sessionId}`;
  }
  return new WebSocket(wsUrl);
}

// ----- Callsigns -----
export interface CallsignEntry {
  callsign?: string;
  id?: number;
  source?: string;
}
export async function listCallsigns(): Promise<{ registered: CallsignEntry[]; count: number }> {
  const res = await fetch(`${API_BASE}/callsigns`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to list callsigns');
  return res.json();
}

export async function registerCallsign(callsign: string, source: string = 'api'): Promise<{ ok: boolean; callsign: string; id: number }> {
  const res = await fetch(`${API_BASE}/callsigns/register`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ callsign: callsign.trim().toUpperCase(), source }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to register callsign');
  return res.json();
}

export async function unregisterCallsign(callsign: string): Promise<{ ok: boolean }> {
  const normalized = callsign.trim().toUpperCase();
  const res = await fetch(`${API_BASE}/callsigns/registered/${encodeURIComponent(normalized)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to unregister');
  return res.json();
}

export async function registerCallsignFromAudio(file: File, callsign?: string): Promise<{ ok: boolean; callsign: string; id: number; transcript?: string }> {
  const form = new FormData();
  form.append('file', file);
  const headers: Record<string, string> = {};
  if (runtimeToken ?? import.meta.env.VITE_RADIOSHAQ_TOKEN) {
    headers['Authorization'] = `Bearer ${runtimeToken ?? import.meta.env.VITE_RADIOSHAQ_TOKEN}`;
  }
  const url = callsign ? `${API_BASE}/callsigns/register-from-audio?callsign=${encodeURIComponent(callsign.trim().toUpperCase())}` : `${API_BASE}/callsigns/register-from-audio`;
  const res = await fetch(url, { method: 'POST', headers, body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to register from audio');
  return res.json();
}

// ----- Messages -----
export async function processMessage(body: { message?: string; text?: string; channel?: string; chat_id?: string; sender_id?: string }): Promise<{ success: boolean; message: string; task_id?: string }> {
  const res = await fetch(`${API_BASE}/messages/process`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to process message');
  return res.json();
}

export async function whitelistRequest(body: { text?: string; message?: string; callsign?: string; send_audio_back?: boolean }): Promise<{ success: boolean; message?: string; approved?: boolean; audio_sent?: boolean; task_id?: string }> {
  const res = await fetch(`${API_BASE}/messages/whitelist-request`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to whitelist request');
  return res.json();
}

export async function injectMessage(body: {
  text: string;
  band?: string;
  frequency_hz?: number;
  mode?: string;
  source_callsign?: string;
  destination_callsign?: string;
}): Promise<{ ok: boolean; qsize?: number }> {
  const res = await fetch(`${API_BASE}/inject/message`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to inject');
  return res.json();
}

/** Inject into RX queue and store transcript (whitelist enforced). Source/dest must be allowed. */
export async function injectAndStore(body: {
  text: string;
  band?: string;
  frequency_hz?: number;
  mode?: string;
  source_callsign?: string;
  destination_callsign?: string;
  metadata?: Record<string, unknown>;
}): Promise<{ ok: boolean; transcript_id?: number; qsize?: number }> {
  const res = await fetch(`${API_BASE}/messages/inject-and-store`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to inject and store');
  return res.json();
}

export async function relayMessage(body: {
  message: string;
  source_band: string;
  target_band: string;
  source_callsign?: string;
  destination_callsign?: string;
  source_frequency_hz?: number;
  target_frequency_hz?: number;
  session_id?: string;
}): Promise<{ ok: boolean; source_transcript_id?: number; relayed_transcript_id?: number; source_band: string; target_band: string }> {
  const res = await fetch(`${API_BASE}/messages/relay`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to relay');
  return res.json();
}

// ----- Transcripts -----
export interface TranscriptItem {
  id?: number;
  transcript_id?: number;
  source_callsign?: string;
  destination_callsign?: string;
  transcript_text?: string;
  frequency_hz?: number;
  mode?: string;
  extra_data?: Record<string, unknown>;
  created_at?: string;
}
export async function searchTranscripts(params?: { callsign?: string; band?: string; mode?: string; since?: string; limit?: number }): Promise<{ transcripts: TranscriptItem[]; count: number }> {
  const search = new URLSearchParams();
  if (params?.callsign) search.set('callsign', params.callsign);
  if (params?.band) search.set('band', params.band);
  if (params?.mode) search.set('mode', params.mode);
  if (params?.since) search.set('since', params.since);
  if (params?.limit != null) search.set('limit', String(params.limit));
  const res = await fetch(`${API_BASE}/transcripts?${search}`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to search transcripts');
  return res.json();
}

export async function getTranscript(id: number): Promise<TranscriptItem> {
  const res = await fetch(`${API_BASE}/transcripts/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to get transcript');
  return res.json();
}

export async function playTranscript(id: number): Promise<{ ok: boolean; transcript_id: number }> {
  const res = await fetch(`${API_BASE}/transcripts/${id}/play`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to play');
  return res.json();
}

// ----- Radio -----
export interface RadioStatusResponse {
  connected: boolean;
  reason?: string;
  frequency_hz?: number;
  mode?: string;
  ptt?: boolean;
}
export async function getRadioStatus(): Promise<RadioStatusResponse> {
  const res = await fetch(`${API_BASE}/radio/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to get radio status');
  return res.json();
}

export async function listBands(): Promise<{ bands: string[] }> {
  const res = await fetch(`${API_BASE}/radio/bands`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to list bands');
  return res.json();
}

export async function sendTts(body: { message: string; frequency_hz?: number; mode?: string }): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/radio/send-tts`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to send TTS');
  return res.json();
}
