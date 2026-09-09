// Shared presentational primitives for the redesign. Rendering only — no
// financial logic lives here (AGENTS.md boundary).

import type { CSSProperties, ReactNode } from "react";

export function IconChart({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="12" width="4" height="9" rx="1" />
      <rect x="10" y="6" width="4" height="15" rx="1" />
      <rect x="17" y="10" width="4" height="11" rx="1" />
    </svg>
  );
}

export function IconLayers({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 2 8.5 12 14l10-5.5L12 3z" />
      <path d="m2 14 10 5.5L22 14" />
    </svg>
  );
}

export function IconPlay({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m6 4 14 8-14 8V4z" />
    </svg>
  );
}

export function IconCompare({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3h4v4" />
      <path d="M21 3l-7 7" />
      <path d="M7 21H3v-4" />
      <path d="M3 21l7-7" />
    </svg>
  );
}

export function IconSpark({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v3m0 12v3m-9-9h3m12 0h3m-4.6-6.4-2.1 2.1m-4.6 4.6-2.1 2.1m11.3 0-2.1-2.1m-4.6-4.6-2.1-2.1" />
      <circle cx="12" cy="12" r="2.2" />
    </svg>
  );
}

export function IconTrend({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 17l6-6 4 4 8-8" />
      <path d="M15 7h6v6" />
    </svg>
  );
}

export function IconCoin({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10M15.5 9.5c0-1.2-1.6-2-3.5-2s-3.5.8-3.5 2 1 1.8 3.5 2.3 3.5 1.1 3.5 2.2-1.6 2-3.5 2-3.5-.8-3.5-2" />
    </svg>
  );
}

export function IconDatabase({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
      <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </svg>
  );
}

export function IconAlert({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 9v4m0 4h.01" />
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </svg>
  );
}

export function IconInfo({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-4m0-4h.01" />
    </svg>
  );
}

export function IconInbox({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.4 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.4-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.8 1.1z" />
    </svg>
  );
}

export function Badge({ kind, children }: { kind: "ok" | "bad" | "accent" | "neutral"; children: ReactNode }) {
  const cls = kind === "neutral" ? "badge" : `badge ${kind}`;
  return <span className={cls}>{children}</span>;
}

export function DirBadge({ direction }: { direction: string }) {
  return <span className={`dir-badge ${direction === "long" ? "long" : "short"}`}>{direction.toUpperCase()}</span>;
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="loading">
      <span className="spinner" />
      {text}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <IconInbox size={28} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return (
    <p className="banner danger">
      <IconAlert size={16} />
      <span>{message}</span>
    </p>
  );
}

export function StatCard({
  label,
  value,
  sub,
  ico,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  ico: ReactNode;
  tone?: "neutral" | "up" | "down";
}) {
  return (
    <div className="card stat-card">
      <div className={`stat-ico ${tone}`}>{ico}</div>
      <div>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

export function MetricCard({ label, value, note, large, className, style }: { label: string; value: string; note?: string; large?: boolean; className?: string; style?: CSSProperties }) {
  return (
    <div className={`card metric${className ? ` ${className}` : ""}`} style={style}>
      <div className="metric-label">
        {label}
        {note && <small>· {note}</small>}
      </div>
      <div className={`metric-value${large ? " lg" : ""}`}>{value}</div>
    </div>
  );
}

export function PageHead({ title, sub, children }: { title: ReactNode; sub?: string; children?: ReactNode }) {
  return (
    <div className="page">
      <h2 className="page-title">{title}</h2>
      {sub && <p className="page-sub">{sub}</p>}
      {children && <div className="page-actions">{children}</div>}
    </div>
  );
}
