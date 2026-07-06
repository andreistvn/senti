export type AdminMfaMethod = 'otp' | 'fingerprint' | 'face';

export interface AdminSession {
  authenticated: boolean;
  digitalId: string | null;
}

export interface AdminAgent {
  id: string;
  name: string;
  ip: string;
  mac: string;
  state: 'PROTECTED' | 'DETECTING' | 'SYNCING';
  syncProgress: number;
  cpu: number;
  ram: number;
  connectedSince: string;
  packetsProcessed: number;
}

export interface AdminLogEntry {
  id: number;
  timestamp: string;
  message: string;
}

export interface AdminLedgerEntry {
  blockId: string;
  timestamp: string;
  macHash: string;
  score: string;
}

export interface AdminTelemetry {
  cpu: number;
  ram: number;
  latency: number;
}

export interface AdminTelemetrySummary extends AdminTelemetry {
  blockHeight: number;
  lastSyncTime: string;
  chainStatus: 'HEALTHY' | 'DEGRADED';
  totalIncidents: number;
}

export interface AdminBlockchainMetrics {
  blockHeight: number;
  lastSyncTime: string;
  chainStatus: 'HEALTHY' | 'DEGRADED';
  totalIncidents: number;
}

export interface AdminThreatPoint {
  time: string;
  pps: number;
  blocked: number;
}

export interface AdminPolicyConfig {
  mlThreshold: number;
  arpFloodLimit: number;
  autoBlacklist: boolean;
  syncInterval: number;
  logRetentionDays: number;
}

export interface AdminDashboardSeed {
  agents: AdminAgent[];
  logs: AdminLogEntry[];
  ledger: AdminLedgerEntry[];
  telemetry: AdminTelemetry;
  blockchainMetrics: AdminBlockchainMetrics;
  threatHistory: AdminThreatPoint[];
  policyConfig: AdminPolicyConfig;
}

const ADMIN_API_BASE_URL = (import.meta.env.VITE_ADMIN_API_BASE_URL ?? '').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 1500;
const SESSION_KEY = 'sentinet.admin.session';

export const ADMIN_CREDENTIALS = {
  digitalId: 'ADM-7734-ALPHA',
  password: 'SentiNet@2049',
  otp: '482910',
} as const;

const ADMIN_DASHBOARD_SEED: AdminDashboardSeed = {
  agents: [
    { id: 'A', name: 'Agent Alpha', ip: '192.168.10.101', mac: 'AA:BB:CC:DD:EE:01', state: 'PROTECTED', syncProgress: 0, cpu: 18, ram: 42, connectedSince: '08:14:02', packetsProcessed: 142830 },
    { id: 'B', name: 'Agent Bravo', ip: '192.168.10.102', mac: 'AA:BB:CC:DD:EE:02', state: 'PROTECTED', syncProgress: 0, cpu: 22, ram: 51, connectedSince: '08:14:07', packetsProcessed: 138420 },
    { id: 'C', name: 'Agent Charlie', ip: '192.168.10.103', mac: 'AA:BB:CC:DD:EE:03', state: 'PROTECTED', syncProgress: 0, cpu: 15, ram: 37, connectedSince: '08:15:11', packetsProcessed: 159012 },
    { id: 'D', name: 'Agent Delta', ip: '192.168.10.104', mac: 'AA:BB:CC:DD:EE:04', state: 'PROTECTED', syncProgress: 0, cpu: 31, ram: 58, connectedSince: '08:15:33', packetsProcessed: 121765 },
  ],
  logs: [
    { id: 1, timestamp: '14:30:00', message: 'SYSTEM: POC-Control-Hub Initialized.' },
    { id: 2, timestamp: '14:30:02', message: 'NETWORK: MultiChain connected successfully.' },
    { id: 3, timestamp: '14:30:05', message: 'SOCKET: Listening on port 8080.' },
  ],
  ledger: [
    { blockId: '0x8A12', timestamp: '14:28:11', macHash: 'FD:09:A1:XX', score: '98.2%' },
    { blockId: '0x8A13', timestamp: '14:29:05', macHash: 'E2:11:4B:XX', score: '94.5%' },
  ],
  telemetry: { cpu: 12, ram: 44, latency: 14 },
  blockchainMetrics: {
    blockHeight: 33912,
    lastSyncTime: '14:30:05',
    chainStatus: 'HEALTHY',
    totalIncidents: 47,
  },
  threatHistory: Array.from({ length: 20 }, (_, i) => ({
    time: `${String(14 + Math.floor(i / 4)).padStart(2, '0')}:${String((i * 15) % 60).padStart(2, '0')}:00`,
    pps: Math.floor(Math.random() * 180) + 40,
    blocked: Math.floor(Math.random() * 140) + 30,
  })),
  policyConfig: {
    mlThreshold: 0.50,
    arpFloodLimit: 1000,
    autoBlacklist: false,
    syncInterval: 4000,
    logRetentionDays: 30,
  },
};

function cloneSeed(): AdminDashboardSeed {
  return {
    agents: ADMIN_DASHBOARD_SEED.agents.map(agent => ({ ...agent })),
    logs: ADMIN_DASHBOARD_SEED.logs.map(entry => ({ ...entry })),
    ledger: ADMIN_DASHBOARD_SEED.ledger.map(entry => ({ ...entry })),
    telemetry: { ...ADMIN_DASHBOARD_SEED.telemetry },
    blockchainMetrics: { ...ADMIN_DASHBOARD_SEED.blockchainMetrics },
    threatHistory: ADMIN_DASHBOARD_SEED.threatHistory.map(point => ({ ...point })),
    policyConfig: { ...ADMIN_DASHBOARD_SEED.policyConfig },
  };
}

export function getAdminDashboardSeedFallback() {
  return cloneSeed();
}

function readSession(): AdminSession {
  if (typeof window === 'undefined') {
    return { authenticated: false, digitalId: null };
  }

  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return { authenticated: false, digitalId: null };
    const parsed = JSON.parse(raw) as AdminSession;
    return {
      authenticated: Boolean(parsed.authenticated),
      digitalId: parsed.digitalId ?? null,
    };
  } catch {
    return { authenticated: false, digitalId: null };
  }
}

function writeSession(session: AdminSession) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${ADMIN_API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });

    if (!response.ok) {
      throw new Error(`Request failed for ${path}: ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

async function requestWithFallback<T>(path: string, fallback: () => T, init?: RequestInit): Promise<T> {
  try {
    return await request<T>(path, init);
  } catch {
    return fallback();
  }
}

export async function getAdminSession() {
  try {
    return await request<AdminSession>('/auth/me');
  } catch {
    return readSession();
  }
}

export async function isAdminAuthenticated() {
  return (await getAdminSession()).authenticated;
}

export function validateAdminCredentials(digitalId: string, password: string) {
  return digitalId === ADMIN_CREDENTIALS.digitalId && password === ADMIN_CREDENTIALS.password;
}

export function validateAdminOtp(otp: string) {
  return otp === ADMIN_CREDENTIALS.otp;
}

export async function signInAdmin(digitalId: string) {
  const session = { authenticated: true, digitalId };
  try {
    await request<AdminSession>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ digitalId }),
    });
  } catch {
    // fall through to local session storage
  }
  writeSession(session);
  return session;
}

export async function signOutAdmin() {
  try {
    await request<void>('/auth/logout', { method: 'POST' });
  } catch {
    // fall through to local session storage
  }
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(SESSION_KEY);
  }
}

export async function getAdminDashboardSeed() {
  const fallback = cloneSeed();
  const [agents, logs, ledger, summary, threatHistory, policyConfig] = await Promise.all([
    requestWithFallback('/agents', () => fallback.agents),
    requestWithFallback('/threats', () => fallback.logs),
    requestWithFallback('/ledger', () => fallback.ledger),
    requestWithFallback<AdminTelemetrySummary>('/telemetry/summary', () => ({
      ...fallback.telemetry,
      ...fallback.blockchainMetrics,
    })),
    requestWithFallback('/analytics/threat-volume', () => fallback.threatHistory),
    requestWithFallback('/policy', () => fallback.policyConfig),
  ]);

  return {
    agents,
    logs,
    ledger,
    telemetry: {
      cpu: summary.cpu,
      ram: summary.ram,
      latency: summary.latency,
    },
    blockchainMetrics: {
      blockHeight: summary.blockHeight,
      lastSyncTime: summary.lastSyncTime,
      chainStatus: summary.chainStatus,
      totalIncidents: summary.totalIncidents,
    },
    threatHistory,
    policyConfig,
  } satisfies AdminDashboardSeed;
}