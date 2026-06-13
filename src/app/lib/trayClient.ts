/**
 * Client for the local SentiNet tray daemon (tray-app/, Python pystray).
 *
 * The tray exposes a loopback JSON API on 127.0.0.1:8770. When the tray app is
 * running on the user's machine, the dashboard reads live state from it; when it
 * isn't, every call rejects fast (short timeout) and the dashboard falls back to
 * its built-in mock data. Keep BASE_URL in sync with tray-app/config.py.
 */
export const BASE_URL = 'http://127.0.0.1:8770';

export interface TrayStatus {
  protected: boolean;
  relay: 'online' | 'offline';
  version: string;
  since: string | null;
}

export interface TrayLastThreat {
  attackType: string;
  sourceMac: string;
  timestamp: string;
}

export interface TrayStats {
  inspected: number;
  dropped: number;
  passed: number;
  blocked: number;
  cpu: number;
  memory: number;
  bayanihan: { contributions: number; usersProtected: number };
  lastThreat: TrayLastThreat | null;
  protected: boolean;
}

export interface TrayEvent {
  id: number;
  timestamp: string;
  sourceMac: string;
  attackType: string;
  tier: string;
  action: string;
}

export interface TrayService {
  id: string;
  name: string;
  status: 'active' | 'loaded' | 'connected' | 'degraded' | 'offline';
  detail: string;
  uptime: string;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 1500): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}${path}`, { ...init, signal: controller.signal });
    if (!res.ok) throw new Error(`tray ${path} → ${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const getStatus = () => request<TrayStatus>('/api/status');
export const getStats = () => request<TrayStats>('/api/stats');
export const getEvents = () =>
  request<{ events: TrayEvent[] }>('/api/events').then(r => r.events);
export const getHealth = () =>
  request<{ services: TrayService[] }>('/api/health').then(r => r.services);
export const toggle = () => request<TrayStatus>('/api/toggle', { method: 'POST' });
