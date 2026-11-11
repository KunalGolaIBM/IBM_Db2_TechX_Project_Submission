/**
 * Display formatters. The backend contract (§1) says: USD has 2 decimals, COUNT is an integer,
 * RATIO is a fraction (0.0767 = 7.67 %), and `null` means "undefined", never zero.
 */

export const UNDEFINED_VALUE = "—";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const usdCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const integerCompact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

export function formatValue(value: number | null | undefined, unit: string | null | undefined, scale?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return UNDEFINED_VALUE;
  switch (unit) {
    case "USD":
      return usd.format(value);
    case "COUNT":
      return integer.format(value);
    case "RATIO": {
      const digits = scale && scale > 0 ? Math.min(scale, 4) : 2;
      return `${(value * 100).toFixed(Math.min(digits, 2))}%`;
    }
    default:
      return String(value);
  }
}

/** Short form for chart axes. */
export function formatAxis(value: number, unit: string | null | undefined): string {
  switch (unit) {
    case "USD":
      return Math.abs(value) >= 10_000 ? usdCompact.format(value) : usd.format(value).replace(/\.00$/, "");
    case "COUNT":
      return Math.abs(value) >= 10_000 ? integerCompact.format(value) : integer.format(value);
    case "RATIO":
      return `${(value * 100).toFixed(value * 100 < 10 ? 1 : 0)}%`;
    default:
      return String(value);
  }
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return UNDEFINED_VALUE;
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 10) return `${Math.round(ms)} ms`;
  return `${ms.toFixed(1)} ms`;
}

/** Audit timestamps have no offset and are UTC (contract §7); analyze timestamps carry `Z`. */
export function parseUtc(value: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

const dateTime = new Intl.DateTimeFormat("en-US", {
  month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
});

export function formatTimestamp(value: string): string {
  const d = parseUtc(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${dateTime.format(d)} UTC`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-01-01" → "Jan 1, 2026" (no timezone arithmetic: dates are plain calendar dates). */
export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${Number(m[3])}, ${m[1]}`;
}

export function formatDateRange(start: string, end: string): string {
  return `${formatDate(start)} – ${formatDate(end)}`;
}

/** "2026-03" → "Mar 2026"; other category values are returned unchanged. */
export function formatCategory(value: unknown): string {
  if (value === null || value === undefined) return UNDEFINED_VALUE;
  const s = String(value);
  const m = /^(\d{4})-(\d{2})$/.exec(s);
  if (m) return `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`;
  return s.replace(/_/g, " ");
}

export function shortHash(hash: string, n = 10): string {
  return hash.length > n ? `${hash.slice(0, n)}…` : hash;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Check names are snake_case identifiers; keep acronyms upper-case ("sql_guard" → "SQL guard"). */
export function checkName(name: string): string {
  const words = name.split("_").map((w) => (w.toLowerCase() === "sql" ? "SQL" : w));
  const joined = words.join(" ");
  return joined.charAt(0).toUpperCase() + joined.slice(1);
}
