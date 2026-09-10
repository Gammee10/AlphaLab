import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { navigate } from "../router";
import { errText, useUi } from "../store";
import { ConditionBuilder } from "../components/ConditionBuilder";
import {
  Badge,
  Banner,
  CopyChip,
  ErrorInline,
  Loading,
  PageHead,
  SectionLabel,
  TabBar,
} from "../components/ui";
import { IcCode, IcLayers, IcList, IcPlay } from "../components/icons";
import { countLeaves, describeNode, maxDepth, type Node } from "../conditions";
import { shortHash } from "../format";

interface EditorState {
  direction: string;
  logic: "all" | "any";
  conditions: Node[];
  stopMult: number;
  takeProfitRatio: number | null;
  riskPct: number;
  sessionOn: boolean;
  sessionStart: number;
  sessionEnd: number;
  oppositeExit: boolean;
}

function fromSpec(spec: Record<string, unknown>): EditorState {
  const entry = spec.entry as { direction: string; logic: "all" | "any"; conditions: Node[] };
  const exits = spec.exits as {
    stopLoss: { atrMultiplier?: number };
    takeProfit: { ratio?: number; kind: string };
    oppositeSignalExit: boolean;
  };
  const risk = spec.risk as { riskPerTradePct: number };
  const filters = (spec.filters ?? {}) as { session?: { kind: string; startHourUtc?: number; endHourUtc?: number } };
  return {
    direction: entry.direction,
    logic: entry.logic,
    conditions: entry.conditions,
    stopMult: exits.stopLoss.atrMultiplier ?? 1.5,
    takeProfitRatio: exits.takeProfit.kind === "rr" ? (exits.takeProfit.ratio as number) : null,
    riskPct: risk.riskPerTradePct,
    sessionOn: filters.session?.kind === "window",
    sessionStart: filters.session?.startHourUtc ?? 7,
    sessionEnd: filters.session?.endHourUtc ?? 20,
    oppositeExit: exits.oppositeSignalExit,
  };
}

const TABS = [
  { id: "rules", label: "Rules & versions", icon: <IcList size={14} /> },
  { id: "build", label: "Visual editor", icon: <IcLayers size={14} /> },
  { id: "json", label: "JSON editor", icon: <IcCode size={14} /> },
];

export function StrategyDetail({ id }: { id: string }) {
  const detail = useQuery({ queryKey: ["strategy", id], queryFn: () => api.strategy(id), enabled: id !== "" });
  const client = useQueryClient();
  const { toast } = useUi();

  const [tab, setTab] = useState("rules");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  const save = useMutation({
    mutationFn: (spec: unknown) => api.createVersion(id, spec),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["strategy", id] });
      client.invalidateQueries({ queryKey: ["strategies"] });
      setDraft("");
      setEditor(null);
      setError("");
      setTab("rules");
      toast("New version saved — history preserved", "ok");
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
  });

  if (id === "") return <ErrorInline text="No strategy id in the URL." />;
  if (detail.isLoading) return <Loading text="Loading strategy…" />;
  if (detail.isError) return <ErrorInline text="Failed to load strategy." />;

  const { strategy, versions } = detail.data!;
  const current = versions[versions.length - 1];
  const spec = current.spec as { indicators: { id: string; kind: string }[] } & Record<string, unknown>;
  const ed = editor ?? fromSpec(current.spec);

  const buildSpec = (): Record<string, unknown> => ({
    ...current.spec,
    entry: { direction: ed.direction, logic: ed.logic, conditions: ed.conditions },
    exits: {
      ...(current.spec.exits as object),
      stopLoss: { kind: "atr", atrMultiplier: ed.stopMult },
      takeProfit: ed.takeProfitRatio === null ? { kind: "none" } : { kind: "rr", ratio: ed.takeProfitRatio },
      oppositeSignalExit: ed.oppositeExit,
    },
    filters: {
      ...((current.spec.filters ?? {}) as object),
      session: ed.sessionOn
        ? { kind: "window", startHourUtc: ed.sessionStart, endHourUtc: ed.sessionEnd }
        : { kind: "none" },
    },
    risk: { ...((current.spec.risk ?? {}) as object), riskPerTradePct: ed.riskPct },
  });

  const leaves = countLeaves(ed.conditions);
  const depth = maxDepth(ed.conditions);
  const validTree = leaves >= 1 && leaves <= 12 && depth <= 3;

  return (
    <div>
      <PageHead
        title={
          <>
            {strategy.name} <Badge kind="neutral">{versions.length} versions</Badge>
          </>
        }
        sub="Immutable version history — every edit creates a new version, nothing is rewritten."
        actions={
          <button className="btn primary" onClick={() => navigate(`/launcher/${current.id}`)}>
            <IcPlay size={14} />
            Backtest current
          </button>
        }
      />

      <TabBar tabs={TABS} active={tab} onChange={(t) => { setTab(t); setError(""); }} />

      {tab === "rules" && (
        <>
          <SectionLabel>Current version</SectionLabel>
          <div className="glass">
            <div className="row-wrap" style={{ marginBottom: "0.6rem" }}>
              <Badge kind="acc">v{current.versionNumber}</Badge>
              <CopyChip text={current.specHash} label={shortHash(current.specHash)} />
              <span className="faint" style={{ fontSize: "0.8rem" }}>spec hash</span>
            </div>
            <div>
              {(current.spec.entry as { conditions: Node[] }).conditions.map((c) => (
                <span key={c.id} className="rule-chip">
                  {describeNode(c)}
                </span>
              ))}
            </div>
          </div>

          <SectionLabel>Version timeline</SectionLabel>
          <div className="glass">
            <ol className="timeline">
              {versions.map((v) => (
                <li key={v.id} className={`timeline-row${v.id === current.id ? " current" : ""}`}>
                  <span className="timeline-dot" />
                  <span className="mono" style={{ fontWeight: 700 }}>v{v.versionNumber}</span>
                  <code>{shortHash(v.specHash)}</code>
                  {v.id === current.id && <Badge kind="ok">current</Badge>}
                  <span className="grow" />
                  <button className="btn glass sm" onClick={() => navigate(`/launcher/${v.id}`)}>
                    <IcPlay size={12} />
                    Backtest
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </>
      )}

      {tab === "build" && (
        <div className="glass" style={{ maxWidth: 820 }}>
          <h4 className="glass-title" style={{ marginBottom: "0.6rem" }}>
            Entry conditions <span className="step-hint">— saving creates a new version</span>
          </h4>
          <div className="field-row">
            <label className="field">
              <span className="field-label">Direction</span>
              <select value={ed.direction} onChange={(e) => setEditor({ ...ed, direction: e.target.value })}>
                <option value="long">long</option>
                <option value="short">short</option>
                <option value="both">both</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Logic</span>
              <select value={ed.logic} onChange={(e) => setEditor({ ...ed, logic: e.target.value as "all" | "any" })}>
                <option value="all">ALL (AND)</option>
                <option value="any">ANY (OR)</option>
              </select>
            </label>
          </div>
          <ConditionBuilder nodes={ed.conditions} indicators={spec.indicators} onChange={(conditions) => setEditor({ ...ed, conditions })} />

          <hr />
          <h4 className="glass-title" style={{ margin: "0.8rem 0 0.4rem" }}>Risk &amp; exits</h4>
          <div className="field-row">
            <label className="field">
              <span className="field-label">Stop (ATR ×)</span>
              <input type="number" step="any" value={ed.stopMult} onChange={(e) => setEditor({ ...ed, stopMult: Number(e.target.value) })} />
            </label>
            <label className="field">
              <span className="field-label">Target (R, blank = none)</span>
              <input
                type="number"
                step="any"
                placeholder="none"
                value={ed.takeProfitRatio ?? ""}
                onChange={(e) => setEditor({ ...ed, takeProfitRatio: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span className="field-label">Risk %</span>
              <input type="number" step="any" value={ed.riskPct} onChange={(e) => setEditor({ ...ed, riskPct: Number(e.target.value) })} />
            </label>
          </div>
          <div className="field-row">
            <label className="check">
              <input type="checkbox" checked={ed.sessionOn} onChange={(e) => setEditor({ ...ed, sessionOn: e.target.checked })} />
              Session filter (UTC)
            </label>
            {ed.sessionOn && (
              <>
                <label className="field">
                  <span className="field-label">Start hour</span>
                  <input type="number" value={ed.sessionStart} onChange={(e) => setEditor({ ...ed, sessionStart: Number(e.target.value) })} />
                </label>
                <label className="field">
                  <span className="field-label">End hour</span>
                  <input type="number" value={ed.sessionEnd} onChange={(e) => setEditor({ ...ed, sessionEnd: Number(e.target.value) })} />
                </label>
              </>
            )}
            <label className="check">
              <input type="checkbox" checked={ed.oppositeExit} onChange={(e) => setEditor({ ...ed, oppositeExit: e.target.checked })} />
              Exit on opposite signal
            </label>
          </div>

          {!validTree && <ErrorInline text={`Tree needs 1–12 conditions, depth ≤ 3 (now ${leaves} leaves, depth ${depth}).`} />}
          {error && <ErrorInline text={error} />}
          <div style={{ marginTop: "0.9rem" }}>
            <button className="btn primary" disabled={!validTree || save.isPending} onClick={() => { setError(""); save.mutate(buildSpec()); }}>
              {save.isPending ? "Saving…" : "Save as new version"}
            </button>
          </div>
        </div>
      )}

      {tab === "json" && (
        <div className="glass" style={{ maxWidth: 820 }}>
          <Banner kind="info">
            Paste the full edited spec JSON. The server validates it against the canonical schema before creating a version.
          </Banner>
          <textarea rows={12} placeholder="{ …full spec json… }" value={draft} onChange={(e) => setDraft(e.target.value)} />
          {error && <ErrorInline text={error} />}
          <div style={{ marginTop: "0.8rem" }}>
            <button
              className="btn primary"
              disabled={!draft || save.isPending}
              onClick={() => {
                setError("");
                try {
                  save.mutate(JSON.parse(draft));
                } catch {
                  setError("Invalid JSON — fix the syntax and try again.");
                  toast("Invalid JSON", "error");
                }
              }}
            >
              {save.isPending ? "Saving…" : "Save as new version"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
