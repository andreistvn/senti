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
  state: 'PROTECTED' | 'DETECTING' | 'SYNCING' | 'UNPROTECTED';
  syncProgress: number;
  cpu: number;
  ram: number;                        // percent of the agent machine's RAM in use, host-wide
  ramMb?: number | null;              // the SentiNet agent process's own RAM, MB
  ramProcessPercent?: number | null;  // that as a share of the agent machine's RAM
  connectedSince: string;
  packetsProcessed: number;
}

export interface AdminLogEntry {
  id: number;
  timestamp: string;
  message: string;
}

export interface AdminBlacklistEntry {
  mac: string;
  firstSeen: string;
  reportedBy: string;
  attackType: string;
  confidence: string;
  tier: string;
}

export interface AdminLedgerEntry {
  blockId: string;
  timestamp: string;
  macHash: string;
  score: string;
}

export interface AdminTelemetry {
  cpu: number;
  ram: number;         // percent of host RAM in use on the relay machine
  ramMb: number;       // host RAM in use, MB
  ramTotalMb: number;  // host RAM installed, MB
  latency: number;
}

export interface AdminTelemetrySummary extends AdminTelemetry {
  blockHeight: number;
  lastSyncTime: string;
  chainStatus: 'HEALTHY' | 'DEGRADED';
  totalIncidents: number;
  connectedAgents: number;
}

export interface AdminBlockchainMetrics {
  blockHeight: number;
  lastSyncTime: string;
  chainStatus: 'HEALTHY' | 'DEGRADED';
  totalIncidents: number;
  connectedAgents: number;
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
  blacklist: AdminBlacklistEntry[];
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
  agents: [],
  logs: [],
  ledger: [],
  blacklist: [],
  telemetry: { cpu: 0, ram: 0, ramMb: 0, ramTotalMb: 0, latency: 0 },
  blockchainMetrics: {
    blockHeight: 0,
    lastSyncTime: '--:--:--',
    chainStatus: 'HEALTHY',
    totalIncidents: 0,
    connectedAgents: 0,
  },
  threatHistory: [],
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
    blacklist: ADMIN_DASHBOARD_SEED.blacklist.map(entry => ({ ...entry })),
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
      credentials: 'include',
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

export type SopScenario = 'normal' | 'poisoning' | 'flooding';

export interface SopEfficiencyScenario {
  n: number;
  meanCpu: number | null;
  varianceCpu: number | null;
  meanRamMb: number | null;
  varianceRamMb: number | null;
  live: boolean;
}

// Computed by the agent at start-up, from the held-out test set.
export interface SopEvaluation {
  threshold: number;
  n: number;
  truePositives: number;
  falsePositives: number;
  trueNegatives: number;
  falseNegatives: number;
  accuracy: number;
  detectionRate: number;
  falsePositiveRate: number;
}

export interface SopTtbTrial {
  attackerMac: string;
  detectedBy: string;
  enforcedBy: string | null;
  tDetectedMs: number;
  tEnforcedMs: number | null;
  ttbMs: number | null;
  relayTtbMs: number | null;
}

export interface SopSummary {
  efficiency: {
    agent: string | null;  // the one agent these figures come from
    scenarios: Record<SopScenario, SopEfficiencyScenario>;
    sampleIntervalSeconds: number;
  };
  detection: {
    evaluation: SopEvaluation | null;
    blockedAttacks: number;
    totalDetectedAttacks: number;
    preventionRate: number | null;
  };
  timeToBlock: {
    latest: SopTtbTrial | null;
    n: number;
    meanTtbMs: number | null;
    varianceTtbMs: number | null;
  };
}

// Null when the backend is unreachable — the SOP tab then shows its empty state
// rather than invented figures.
export async function getSopSummary() {
  return requestWithFallback<SopSummary | null>('/sop/summary', () => null);
}

export async function getAdminDashboardSeed() {
  const fallback = cloneSeed();
  const [agents, logs, ledger, blacklistResp, summary, threatHistory, policyConfig] = await Promise.all([
    requestWithFallback('/agents', () => fallback.agents),
    requestWithFallback('/threats', () => fallback.logs),
    requestWithFallback('/ledger', () => fallback.ledger),
    requestWithFallback<{ entries: AdminBlacklistEntry[] }>('/blacklist', () => ({ entries: fallback.blacklist })),
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
    blacklist: blacklistResp?.entries ?? [],
    telemetry: {
      cpu: summary.cpu,
      ram: summary.ram,
      ramMb: summary.ramMb ?? 0,
      ramTotalMb: summary.ramTotalMb ?? 0,
      latency: summary.latency,
    },
    blockchainMetrics: {
      blockHeight: summary.blockHeight,
      lastSyncTime: summary.lastSyncTime,
      chainStatus: summary.chainStatus,
      totalIncidents: summary.totalIncidents,
      connectedAgents: summary.connectedAgents ?? 0,
    },
    threatHistory,
    policyConfig,
  } satisfies AdminDashboardSeed;
}