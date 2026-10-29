// Detection model for the Detection Logs and Reports tabs.
//
// /threats sends each detection's fields separately, and also flattened into
// one sentence for the Dashboard's log feed:
//   "[Tier 2] ARP Spoofing from AA:BB:CC:DD:EE:FF. Action: Blocked - detail"
// The fields are used when present. Entries without them (the offline seed,
// browser-side ADMIN/SYSTEM notices) fall back to parsing that sentence.

import type { AdminLogEntry } from './adminApi';

export type RawLog = AdminLogEntry;

export interface Detection {
  id: number;
  timestamp: string;    // HH:MM:SS
  tier: string;         // "Tier-2", or "—" for non-detection events
  attackType: string;   // e.g. "ARP Spoofing"; the full message for non-detections
  sourceMac: string;    // "" when not a detection
  action: string;       // BLOCKED / DETECTED / COUNTED / ...
  detail: string;
  confidence: string;   // "87.3%", "N/A", or "" when unknown
  createdMs: number | null; // epoch ms, relay clock; null when unknown
  raw: string;          // the original message, for search / fallback
  isDetection: boolean; // false for ADMIN / SYSTEM / POLICY notices
}

const DETECTION_RE =
  /^\[([^\]]+)\]\s*(.+?)\s+from\s+(.+?)\.\s*Action:\s*([A-Za-z_]+)(?:\s*-\s*(.*))?$/;

export function parseDetection(log: RawLog): Detection {
  const createdMs = log.createdTs != null ? log.createdTs * 1000 : null;
  if (log.tier && log.sourceMac) {
    return {
      id: log.id,
      timestamp: log.timestamp,
      tier: log.tier,
      attackType: log.attackType ?? 'Unknown',
      sourceMac: log.sourceMac,
      action: (log.action ?? '—').toUpperCase(),
      detail: log.detail ?? '',
      confidence: log.confidence ?? '',
      createdMs,
      raw: log.message,
      isDetection: true,
    };
  }
  const m = log.message.match(DETECTION_RE);
  if (!m) {
    return {
      id: log.id,
      timestamp: log.timestamp,
      tier: '—',
      attackType: log.message,
      sourceMac: '',
      action: '—',
      detail: '',
      confidence: '',
      createdMs,
      raw: log.message,
      isDetection: false,
    };
  }
  return {
    id: log.id,
    timestamp: log.timestamp,
    tier: m[1].trim(),
    attackType: m[2].trim(),
    sourceMac: m[3].trim(),
    action: m[4].trim().toUpperCase(),
    detail: (m[5] ?? '').trim(),
    confidence: '',
    createdMs,
    raw: log.message,
    isDetection: true,
  };
}

export type ActionTone = 'blocked' | 'detected' | 'other';

export function actionTone(action: string): ActionTone {
  const a = action.toUpperCase();
  if (a.includes('BLOCK')) return 'blocked';
  if (a.includes('DETECT') || a.includes('COUNT') || a.includes('REPORT')) return 'detected';
  return 'other';
}

export const ACTION_COLOR: Record<ActionTone, string> = {
  blocked: '#DC2626',
  detected: '#D97706',
  other: '#64748B',
};

// Minimal CSV builder. `columns` maps a header label to a value getter.
export function toCSV<T>(rows: T[], columns: { header: string; get: (row: T) => string | number }[]): string {
  const esc = (v: string | number) => {
    const s = String(v ?? '');
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = columns.map(c => esc(c.header)).join(',');
  const body = rows.map(r => columns.map(c => esc(c.get(r))).join(',')).join('\n');
  return `${head}\n${body}`;
}

export function downloadCSV(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  // Revoking in the same tick can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
