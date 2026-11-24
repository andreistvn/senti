// Shared display formatters for the admin dashboard.

// A duration in milliseconds, shown in the unit that reads cleanly: anything
// at or above 1,000 ms is converted to seconds, smaller values stay in ms.
// Returns the number and its unit separately so callers can style them (e.g.
// the SOP metric cells put the unit in a smaller, muted span).
export function durationParts(
  ms: number | null | undefined,
  msDigits = 0,
  sDigits = 2,
): { value: string | null; unit?: string } {
  if (ms == null || Number.isNaN(ms)) return { value: null };
  if (Math.abs(ms) >= 1000) return { value: (ms / 1000).toFixed(sDigits), unit: 's' };
  return { value: ms.toFixed(msDigits), unit: 'ms' };
}

// Same rule, as a single "<value> <unit>" string for inline sentences.
export function formatDuration(
  ms: number | null | undefined,
  msDigits = 0,
  sDigits = 2,
): string | null {
  const { value, unit } = durationParts(ms, msDigits, sDigits);
  return value == null ? null : `${value} ${unit}`;
}
