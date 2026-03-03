import type { AudioConfig, PendingResponse } from '../types/audio';

const API_BASE = import.meta.env.VITE_RADIOSHAQ_API ?? 'http://localhost:8000';

function getHeaders(): HeadersInit {
  const token = import.meta.env.VITE_RADIOSHAQ_TOKEN;
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function getAudioConfig(): Promise<AudioConfig> {
  const res = await fetch(`${API_BASE}/api/v1/config/audio`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch config');
  return res.json();
}

export async function updateAudioConfig(config: Partial<AudioConfig>): Promise<AudioConfig> {
  const res = await fetch(`${API_BASE}/api/v1/config/audio`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to update config');
  return res.json();
}

export async function listAudioDevices(): Promise<{ input_devices: { index: number; name: string }[]; output_devices: { index: number; name: string }[] }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/devices`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch devices');
  return res.json();
}

export async function listPendingResponses(): Promise<{ pending_responses: PendingResponse[]; count: number }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/pending`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch pending');
  return res.json();
}

export async function approvePendingResponse(pendingId: string, operator?: string): Promise<{ pending: PendingResponse }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/pending/${pendingId}/approve`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ operator }),
  });
  if (!res.ok) throw new Error('Failed to approve');
  return res.json();
}

export async function rejectPendingResponse(pendingId: string, operator?: string, notes?: string): Promise<{ pending: PendingResponse }> {
  const res = await fetch(`${API_BASE}/api/v1/audio/pending/${pendingId}/reject`, {
    method: 'POST',
    headers: getHeaders(),
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
    wsUrl = `${API_BASE.replace(/^http/, 'ws')}/ws/audio/metrics/${sessionId}`;
  }
  return new WebSocket(wsUrl);
}
