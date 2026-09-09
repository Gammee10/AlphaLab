import { useMemo } from "react";
import { toPoints } from "./format";

function path(pts: { t: number; e: number }[], w: number, h: number, pad: number): string {
  if (pts.length === 0) return "";
  const ts = pts.map((p) => p.t);
  const es = pts.map((p) => p.e);
  const t0 = Math.min(...ts);
  const t1 = Math.max(...ts);
  const e0 = Math.min(...es);
  const e1 = Math.max(...es);
  const X = (t: number) => (t1 === t0 ? pad : pad + ((t - t0) / (t1 - t0)) * (w - 2 * pad));
  const Y = (e: number) => (e1 === e0 ? h / 2 : h - pad - ((e - e0) / (e1 - e0)) * (h - 2 * pad));
  return pts.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.t).toFixed(1)},${Y(p.e).toFixed(1)}`).join(" ");
}

export function EquityChart({ curve, width = 640, height = 220 }: { curve: [number, string][]; width?: number; height?: number }) {
  const pts = useMemo(() => toPoints(curve), [curve]);
  const d = useMemo(() => path(pts, width, height, 12), [pts, width, height]);
  if (pts.length === 0) return <p className="muted">No equity data.</p>;
  const last = pts[pts.length - 1].e;
  const first = pts[0].e;
  return (
    <figure>
      <svg width={width} height={height} role="img" aria-label="Equity curve">
        <path d={d} fill="none" stroke={last >= first ? "#1a7f37" : "#b42318"} strokeWidth={1.5} />
      </svg>
      <figcaption className="muted">
        {pts.length} points · {first.toFixed(2)} → {last.toFixed(2)}
      </figcaption>
    </figure>
  );
}

export function OverlayChart({ curves }: { curves: { label: string; points: { t: number; pct: number }[] }[] }) {
  const width = 640;
  const height = 220;
  const all = curves.flatMap((c) => c.points);
  const ts = all.map((p) => p.t);
  const ps = all.map((p) => p.pct);
  const t0 = Math.min(...ts);
  const t1 = Math.max(...ts);
  const lo = Math.min(...ps);
  const hi = Math.max(...ps);
  const colors = ["#1a7f37", "#175cd3", "#b42318", "#7a5af8"];
  return (
    <svg width={width} height={height} role="img" aria-label="Normalized equity overlay">
      {curves.map((c, i) => {
        const d = c.points
          .map((p, j) => {
            const x = t1 === t0 ? 12 : 12 + ((p.t - t0) / (t1 - t0)) * (width - 24);
            const y = hi === lo ? height / 2 : height - 12 - ((p.pct - lo) / (hi - lo)) * (height - 24);
            return `${j === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
          })
          .join(" ");
        return <path key={c.label} d={d} fill="none" stroke={colors[i % colors.length]} strokeWidth={1.5} />;
      })}
    </svg>
  );
}
