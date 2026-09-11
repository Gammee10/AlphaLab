// Reusable presentational primitives. Rendering only — no financial logic.

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type CSSProperties,
} from "react";
import { IcCheck, IcInbox, IcInfo, IcWarn, IcX } from "./icons";
import { useUi } from "../store";

/* ---------- Badges ---------- */
export function Badge({ kind, children }: { kind: "ok" | "bad" | "acc" | "warn" | "info" | "neutral"; children: ReactNode }) {
  const cls = kind === "neutral" ? "badge" : `badge b-${kind}`;
  return <span className={cls}>{children}</span>;
}

export function SidePill({ direction }: { direction: string }) {
  return <span className={`side-pill ${direction === "long" ? "long" : "short"}`}>{direction.toUpperCase()}</span>;
}

/* ---------- States ---------- */
export function Spinner({ size = 15 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size, border: "2px solid var(--border-strong)", borderTopColor: "var(--accent)", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} />;
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="row-wrap" style={{ padding: "1rem 0", color: "var(--text-2)" }}>
      <Spinner />
      {text}
    </div>
  );
}

export function Skeleton({ h, w }: { h?: number | string; w?: number | string }) {
  return <div className="skeleton" style={{ height: h ?? 14, width: w ?? "100%" }} />;
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <IcInbox size={30} />
      </div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div style={{ marginTop: "0.8rem" }}>{action}</div>}
    </div>
  );
}

export function ErrorInline({ text }: { text: string }) {
  return (
    <p className="error-inline">
      <IcWarn size={15} />
      {text}
    </p>
  );
}

/* ---------- Card header ---------- */
export function CardHead({ icon, title, right }: { icon?: ReactNode; title: ReactNode; right?: ReactNode }) {
  return (
    <div className="card-head">
      {icon && <span className="card-icon">{icon}</span>}
      <span className="card-title">{title}</span>
      {right && <span className="card-right">{right}</span>}
    </div>
  );
}

/* ---------- Page header ---------- */
export function PageHead({ eyebrow, title, sub, actions }: { eyebrow?: ReactNode; title: ReactNode; sub?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="grow" style={{ minWidth: 0 }}>
        {eyebrow && <div className="eyebrow" style={{ marginBottom: "0.35rem" }}>{eyebrow}</div>}
        <h2 className="page-title">{title}</h2>
        {sub && <p className="page-sub">{sub}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function SectionLabel({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="section-label">
      {children}
      {right && <span style={{ textTransform: "none", letterSpacing: 0 }}>{right}</span>}
    </div>
  );
}

/* ---------- Banner ---------- */
export function Banner({ kind, children }: { kind: "warn" | "info" | "danger"; children: ReactNode }) {
  const icon = kind === "warn" ? <IcWarn size={15} /> : kind === "danger" ? <IcWarn size={15} /> : <IcInfo size={15} />;
  return (
    <div className={`banner ${kind}`}>
      {icon}
      <div className="banner-body">{children}</div>
    </div>
  );
}

/* ---------- Metric card ---------- */
export function MetricCard({
  label,
  value,
  note,
  large,
  tone,
  className,
  style,
}: {
  label: string;
  value: string;
  note?: string;
  large?: boolean;
  tone?: "up" | "down" | null;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={`glass metric-card${className ? ` ${className}` : ""}`} style={style}>
      <div className="metric-head">
        {label}
        {note && <small>· {note}</small>}
      </div>
      <div className={`metric-value${large ? " lg" : ""}${tone ? ` num-${tone}` : ""}`}>{value}</div>
    </div>
  );
}

/* ---------- Tabs ---------- */
export interface TabDef {
  id: string;
  label: string;
  icon?: ReactNode;
}
export function TabBar({ tabs, active, onChange }: { tabs: TabDef[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="tabbar" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={active === t.id} className={active === t.id ? "active" : ""} onClick={() => onChange(t.id)}>
          {t.icon}
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Modal ---------- */
export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal-box${wide ? " wide" : ""}`}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="x" onClick={onClose} aria-label="Close">
            <IcX size={15} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------- Toasts ---------- */
export function Toaster() {
  const { toasts, dismissToast } = useUi();
  if (toasts.length === 0) return null;
  return (
    <div className="toast-host">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          {t.kind === "ok" ? <IcCheck size={15} /> : t.kind === "error" ? <IcWarn size={15} /> : <IcInfo size={15} />}
          <span>{t.text}</span>
          <button className="close" onClick={() => dismissToast(t.id)} aria-label="Dismiss">
            <IcX size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}

/* ---------- Copy-to-clipboard chip ---------- */
export function CopyChip({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="mono"
      title="Copy to clipboard"
      onClick={() => {
        navigator.clipboard?.writeText(text).catch(() => undefined);
        setDone(true);
        window.setTimeout(() => setDone(false), 1200);
      }}
      style={{
        background: "var(--inset)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "1px 7px",
        fontSize: "0.84em",
        color: done ? "var(--up)" : "var(--accent-2)",
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      {label ?? text}
      {done ? <IcCheck size={11} /> : null}
    </button>
  );
}

/* ---------- Debounced input value hook ---------- */
export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  const t = useRef<number>(0);
  useEffect(() => {
    window.clearTimeout(t.current);
    t.current = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t.current);
  }, [value, ms]);
  return v;
}
