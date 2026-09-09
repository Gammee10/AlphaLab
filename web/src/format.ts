// Pure display helpers. No financial authority: inputs are server strings.
// Covered by vitest.

export function fmtMoney(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  if (!isFinite(n)) return "—";
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return "— (n<30)";
  return value.toFixed(2);
}

/** Downsampled equity points for SVG: [[time, equity]] with string equity. */
export function toPoints(curve: [number, string][]): { t: number; e: number }[] {
  return curve.map(([t, e]) => ({ t, e: Number(e) }));
}

/** Normalize several equity curves to % from their own start for overlay. */
export function normalize(curve: [number, string][]): { t: number; pct: number }[] {
  const pts = toPoints(curve);
  if (pts.length === 0) return [];
  const start = pts[0].e;
  if (start === 0) return pts.map((p) => ({ t: p.t, pct: 0 }));
  return pts.map((p) => ({ t: p.t, pct: ((p.e - start) / Math.abs(start)) * 100 }));
}

export function deltaClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "muted";
  return value > 0 ? "up" : value < 0 ? "down" : "muted";
}

export function shortHash(hash: string): string {
  return hash.slice(0, 8);
}
