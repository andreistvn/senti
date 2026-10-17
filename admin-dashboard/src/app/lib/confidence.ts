// How the admin dashboard reads and colours a model-confidence value.
//
// Confidence is the ML model's probability (0–100%) that a MAC is attacking.
// The ML threshold (policy: mlThreshold, a 0–1 fraction) is the decision line:
// at or above it, a MAC is treated as malicious. A value is only meaningful
// *relative to that line* — 55% is not "5% worse than 50%", it is "just past
// the boundary", where false positives are most likely.

// Accepts "99.9%", "0.95", "95", or "N/A"; returns a 0–100 number, or null.
export function parseConfidence(raw: string | null | undefined): number | null {
  if (raw == null) return null;
  const text = String(raw);
  const match = text.match(/-?\d+(\.\d+)?/);
  if (!match) return null;
  let n = parseFloat(match[0]);
  if (Number.isNaN(n)) return null;
  // A bare 0..1 fraction with no percent sign (e.g. "0.95") means 95%.
  if (n <= 1 && !text.includes('%')) n *= 100;
  return n;
}

export type ConfidenceTone = 'muted' | 'borderline' | 'high';

// Below threshold → would not block (muted). Within 10 points above → borderline
// (false-positive risk). Higher → a strong detection.
export function confidenceTone(
  raw: string | null | undefined,
  thresholdPct: number,
): ConfidenceTone | null {
  const n = parseConfidence(raw);
  if (n == null) return null;
  if (n < thresholdPct) return 'muted';
  if (n < thresholdPct + 10) return 'borderline';
  return 'high';
}

const TONE_COLOR: Record<ConfidenceTone, string> = {
  muted: '#94A3B8',       // slate — below the decision line
  borderline: '#D97706',  // amber — just over, watch for false alarms
  high: '#DC2626',        // red — strong detection
};

export function confidenceColor(
  raw: string | null | undefined,
  thresholdPct: number,
): string {
  const tone = confidenceTone(raw, thresholdPct);
  return tone ? TONE_COLOR[tone] : '#94A3B8';
}

// Shared explanation shown in the column-header tooltips.
export function confidenceLegend(thresholdPct: number): string {
  return (
    `Model certainty this device is attacking (0–100%). ` +
    `The ML threshold is ${thresholdPct.toFixed(0)}% — at or above it a device is treated as malicious. ` +
    `Grey = below the threshold (would not block). ` +
    `Amber = just above it, borderline, so watch for false alarms. ` +
    `Red = a strong, high-confidence detection.`
  );
}
