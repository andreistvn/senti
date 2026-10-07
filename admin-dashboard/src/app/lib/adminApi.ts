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
  policyConfig: AdminPolicyConfig;
}

const ADMIN_API_BASE_URL = (import.meta.env.VITE_ADMIN_API_BASE_URL ?? '').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 1500;

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
    policyConfig: { ...ADMIN_DASHBOARD_SEED.policyConfig },
  };
}

export function getAdminDashboardSeedFallback() {
  return cloneSeed();
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
      // The session expired or was ended elsewhere: back to the sign-in page,
      // rather than leaving the dashboard silently showing empty panels.
      if (response.status === 401 && !path.startsWith('/auth/') && typeof window !== 'undefined'
          && window.location.pathname !== '/') {
        window.location.replace('/');
      }
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

// Authentication is entirely the relay's: it checks the password against its
// hashed account file and sets an HttpOnly session cookie. Nothing here can
// decide on its own that the user is signed in.

export async function getAdminSession(): Promise<AdminSession> {
  try {
    return await request<AdminSession>('/auth/me');
  } catch {
    return { authenticated: false, digitalId: null };
  }
}

export async function isAdminAuthenticated() {
  return (await getAdminSession()).authenticated;
}

export type SignInResult = { ok: true } | { ok: false; message: string };

export async function signInAdmin(digitalId: string, password: string): Promise<SignInResult> {
  const controller = new AbortController();
  // Password hashing on the relay takes a moment; allow longer than other calls.
  const timeoutId = globalThis.setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${ADMIN_API_BASE_URL}/auth/login`, {
      method: 'POST',
      credentials: 'include',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ digitalId, password }),
    });
    if (response.ok) return { ok: true };
    let message = 'Sign-in failed.';
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') message = body.detail;
    } catch {
      // keep the generic message
    }
    return { ok: false, message };
  } catch {
    return { ok: false, message: 'Cannot reach the relay. Check that it is running.' };
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export async function signOutAdmin() {
  try {
    await request<void>('/auth/logout', { method: 'POST' });
  } catch {
    // the cookie is cleared by the relay; nothing else is stored here
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

// The agent's per-packet verdicts scored against the attacker declared for the
// run (start_relay_node.sh --attacker). Rates are null until there is data.
export interface SopLiveMatrix {
  truePositives: number;
  falsePositives: number;
  trueNegatives: number;
  falseNegatives: number;
  n: number;
  accuracy: number | null;
  detectionRate: number | null;
  falsePositiveRate: number | null;
}

// How long Tier 2 took over the reporting agent's most recent detection.
export interface SopDetectionLatency {
  mac: string;
  packets: number;
  ms: number;
}

export interface SopTtbTrial {
  attackerMac: string;
  detectedBy: string;
  enforcedBy: string | null;
  // Both timestamps are on the relay's clock, so they can be compared.
  tDetectedMs: number;
  tEnforcedMs: number | null;
  ttbMs: number | null;
  // The two agents' own clocks subtracted directly — off by however far apart they are.
  agentClockTtbMs: number | null;
}

export interface SopSummary {
  efficiency: {
    agent: string | null;  // the one agent these figures come from
    scenarios: Record<SopScenario, SopEfficiencyScenario>;
    sampleIntervalSeconds: number;
  };
  detection: {
    evaluation: SopEvaluation | null;
    // Attacker MAC(s) declared for this run; empty means no live matrix.
    attackerMacs?: string[];
    live?: SopLiveMatrix | null;
    latency?: SopDetectionLatency | null;
    // Attack packets, counted by the reporting agent. Null until it sends them.
    blockedAttacks: number | null;
    totalDetectedAttacks: number | null;
    preventionRate: number | null;
    // 'kernel' when blocked packets are really dropped; 'simulated' when the
    // agent's platform can only count them.
    enforcement: 'kernel' | 'simulated' | null;
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

// ── Analytics tab ──────────────────────────────────────────────────────────

export interface TrafficLivePoint {
  t: number;                        // epoch ms
  pps: number;                      // ARP packets/s, all agents
  blocked: number;                  // Tier-1 blocks/s, all agents
  agents: Record<string, number>;   // ARP packets/s per agent MAC
}

export interface TrafficAgent {
  mac: string;
  name: string;
  enforcement: 'kernel' | 'simulated';
  pps: number;
  blockedPps: number;
  packets: number;                  // running totals since the agent started
  blocked: number;
}

export interface TrafficPeriodBucket { label: string; packets: number; blocked: number; }
export interface IncidentBucket { label: string; detections: number; blocks: number; }

export interface TrafficAnalytics {
  live: TrafficLivePoint[];
  agents: TrafficAgent[];
  session: {
    currentPps: number;
    currentBlockedPps: number;
    peakPps: number;
    avgPps: number;
    packets: number;
    blocked: number;
    since: number;                  // epoch ms the relay started
  };
  daily: TrafficPeriodBucket[];     // last 24 hours, by hour
  weekly: TrafficPeriodBucket[];    // last 7 days
  monthly: TrafficPeriodBucket[];   // last 30 days
  incidents: IncidentBucket[];      // last 24 hours, by hour
}

// Null when the relay is unreachable; the tab then shows its empty state.
export async function getTrafficAnalytics() {
  return requestWithFallback<TrafficAnalytics | null>('/analytics/traffic', () => null);
}

export async function getAdminDashboardSeed() {
  const fallback = cloneSeed();
  const [agents, logs, ledger, blacklistResp, summary, policyConfig] = await Promise.all([
    requestWithFallback('/agents', () => fallback.agents),
    requestWithFallback('/threats', () => fallback.logs),
    requestWithFallback('/ledger', () => fallback.ledger),
    requestWithFallback<{ entries: AdminBlacklistEntry[] }>('/blacklist', () => ({ entries: fallback.blacklist })),
    requestWithFallback<AdminTelemetrySummary>('/telemetry/summary', () => ({
      ...fallback.telemetry,
      ...fallback.blockchainMetrics,
    })),
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
    policyConfig,
  } satisfies AdminDashboardSeed;
}