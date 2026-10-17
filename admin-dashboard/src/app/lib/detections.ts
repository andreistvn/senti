// Frontend-only detection model.
//
// The backend /threats endpoint flattens each detection into one sentence:
//   "[Tier-2] ARP Spoofing from AA:BB:CC:DD:EE:FF. Action: BLOCKED - detail"
// Until the backend exposes the raw fields, we parse that string back into
// columns here so the admin can show a real detection log, filter it, and
// export it. (A one-line backend serializer change would make this exact.)

export interface RawLog {
  id: number;
  timestamp: string;
  message: string;
}

export interface Detection {
  id: number;
  timestamp: string;    // HH:MM:SS
  tier: string;         // "Tier-2", or "—" for non-detection events
  attackType: string;   // e.g. "ARP Spoofing"; the full message for non-detections
  sourceMac: string;    // "" when not a detection
  action: string;       // BLOCKED / DETECTED / COUNTED / ...
  detail: string;
  raw: string;          // the original message, for search / fallback
  isDetection: boolean; // false for ADMIN / SYSTEM / POLICY notices
}

const DETECTION_RE =
  /^\[([^\]]+)\]\s*(.+?)\s+from\s+(.+?)\.\s*Action:\s*([A-Za-z_]+)(?:\s*-\s*(.*))?$/;

export function parseDetection(log: RawLog): Detection {
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
  URL.revokeObjectURL(url);
}
