/** Display formatting. Everything here is presentation-only — no data is derived. */

export const EM_DASH = '—';
export const NOT_AVAILABLE = 'n/a';

/** Render a possibly-missing string, falling back to an em dash. */
export function text(value: string | null | undefined, fallback = EM_DASH): string {
  if (value === null || value === undefined) return fallback;
  const trimmed = value.trim();
  return trimmed === '' ? fallback : trimmed;
}

/** True when a value carries no usable information. */
export function isBlank(value: string | null | undefined): boolean {
  return value === null || value === undefined || value.trim() === '';
}

/** `2026-09-11` -> `2026-09-11` (already ISO; kept verbatim for the tables). */
export function isoDate(value: string | null | undefined): string {
  return text(value);
}

/** `2026-08` -> `Aug 2026`. */
export function monthLabel(value: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(value.trim());
  if (!match) return value;
  const monthNames = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  const monthIndex = Number(match[2]) - 1;
  const name = monthNames[monthIndex];
  return name ? `${name} ${match[1]}` : value;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return value.toLocaleString('en-US');
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toFixed(digits)}%`;
}

/** `ISO timestamp` -> `2026-10-18 19:24:51Z` (second precision, UTC). */
export function formatUtcTimestamp(value: string | null | undefined): string {
  if (isBlank(value)) return EM_DASH;
  const parsed = new Date(value as string);
  if (Number.isNaN(parsed.getTime())) return text(value);
  const iso = parsed.toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 19)}Z`;
}

/** `HH:MM:SS` in UTC — the header clock. */
export function formatUtcClock(date: Date): string {
  return `${date.toISOString().slice(11, 19)}Z`;
}

/** `YYYY-MM-DD` in UTC — the header date. */
export function formatUtcDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, Math.max(0, max - 1))}…`;
}

/** Sorted, bounded list of `[label, count]` pairs from a count map. */
export function sortedCounts(
  counts: Record<string, number>,
  limit?: number,
): Array<{ label: string; value: number }> {
  const rows = Object.entries(counts)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
  return typeof limit === 'number' ? rows.slice(0, limit) : rows;
}

/** Title-case a snake_case backend field name: `application_date` -> `Application date`. */
export function humaniseField(key: string): string {
  const spaced = key.replace(/_/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
