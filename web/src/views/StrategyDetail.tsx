import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { ConditionBuilder } from "../components/ConditionBuilder";
import { Badge, ErrorNotice, IconPlay, Loading, PageHead } from "../components/ui";
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

export function StrategyDetail({ id, onBacktest }: { id: string; onBacktest: (versionId: string) => void }) {
  const detail = useQuery({ queryKey: ["strategy", id], queryFn: () => api.strategy(id) });
  const [tab, setTab] = useState<"rules" | "build" | "json">("rules");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const client = useQueryClient();

  const save = useMutation({
    mutationFn: (spec: unknown) => api.createVersion(id, spec),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["strategy", id] });
      setDraft("");
      setEditor(null);
      setError("");
      setTab("rules");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  if (detail.isLoading) return <Loading text="Loading strategy…" />;
  if (detail.isError) return <ErrorNotice message="Failed to load strategy." />;
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
      />
      <div className="tabs">
        {(["rules", "build", "json"] as const).map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => {
              setTab(t);
              setError("");
            }}
          >
            {t === "rules" ? "Rules & versions" : t === "build" ? "Visual editor" : "JSON editor"}
          </button>
        ))}
      </div>

      {tab === "rules" && (
        <>
          <div className="card">
            <div style={{ display: "flex", alignItems: "center", gap: "0.7rem", flexWrap: "wrap", marginBottom: "0.7rem" }}>
              <Badge kind="accent">v{current.versionNumber}</Badge>
              <code>{shortHash(current.specHash)}</code>
            </div>
            {(current.spec.entry as { conditions: Node[]; direction: string }).conditions.map((c) => (
              <div key={c.id} className="rule-line">
                {describeNode(c)}
              </div>
            ))}
            <div style={{ marginTop: "1rem" }}>
              <button className="btn primary" onClick={() => onBacktest(current.id)}>
                <IconPlay size={14} />
                Backtest this version
              </button>
            </div>
          </div>
          <h3 className="section-title">Version history (immutable)</h3>
          <ol className="versions">
            {versions.map((v) => (
              <li key={v.id} className={`version-row${v.id === current.id ? " current" : ""}`}>
                <span className="v-num">v{v.versionNumber}</span>
                <code>{shortHash(v.specHash)}</code>
                {v.id === current.id && <Badge kind="ok">current</Badge>}
                <span className="spacer" />
                <button className="btn ghost sm" onClick={() => onBacktest(v.id)}>
                  Backtest
                </button>
              </li>
            ))}
          </ol>
        </>
      )}

      {tab === "build" && (
        <div className="card" style={{ maxWidth: 780 }}>
          <h4 className="card-title">Entry conditions (new version, history preserved)</h4>
          <div className="field-row">
            <label className="field">
              Direction
              <select value={ed.direction} onChange={(e) => setEditor({ ...ed, direction: e.target.value })}>
                <option value="long">long</option>
                <option value="short">short</option>
                <option value="both">both</option>
              </select>
            </label>
            <label className="field">
              Logic
              <select value={ed.logic} onChange={(e) => setEditor({ ...ed, logic: e.target.value as "all" | "any" })}>
                <option value="all">ALL (AND)</option>
                <option value="any">ANY (OR)</option>
              </select>
            </label>
          </div>
          <ConditionBuilder nodes={ed.conditions} indicators={spec.indicators} onChange={(conditions) => setEditor({ ...ed, conditions })} />
          <hr className="divider" />
          <h4 className="card-title">Risk &amp; exits</h4>
          <div className="field-row">
            <label className="field">
              Stop (ATR ×)
              <input type="number" step="any" value={ed.stopMult} onChange={(e) => setEditor({ ...ed, stopMult: Number(e.target.value) })} />
            </label>
            <label className="field">
              Target (R, blank = none)
              <input
                type="number"
                step="any"
                value={ed.takeProfitRatio ?? ""}
                placeholder="none"
                onChange={(e) => setEditor({ ...ed, takeProfitRatio: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </label>
            <label className="field">
              Risk %
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
                  Start hour
                  <input type="number" value={ed.sessionStart} onChange={(e) => setEditor({ ...ed, sessionStart: Number(e.target.value) })} />
                </label>
                <label className="field">
                  End hour
                  <input type="number" value={ed.sessionEnd} onChange={(e) => setEditor({ ...ed, sessionEnd: Number(e.target.value) })} />
                </label>
              </>
            )}
            <label className="check">
              <input type="checkbox" checked={ed.oppositeExit} onChange={(e) => setEditor({ ...ed, oppositeExit: e.target.checked })} />
              Exit on opposite signal
            </label>
          </div>
          {!validTree && <p className="error-text">Tree needs 1–12 conditions, depth ≤ 3 (now {leaves}, depth {depth}).</p>}
          {error && <ErrorNotice message={error} />}
          <button className="btn primary" disabled={!validTree || save.isPending} onClick={() => { setError(""); save.mutate(buildSpec()); }}>
            Save as new version
          </button>
        </div>
      )}

      {tab === "json" && (
        <div className="card" style={{ maxWidth: 780 }}>
          <h4 className="card-title">Advanced: full spec JSON (server-validated)</h4>
          <textarea rows={12} placeholder="Paste the full edited spec…" value={draft} onChange={(e) => setDraft(e.target.value)} />
          {error && <ErrorNotice message={error} />}
          <div style={{ marginTop: "0.7rem" }}>
            <button
              className="btn primary"
              onClick={() => {
                setError("");
                try {
                  save.mutate(JSON.parse(draft));
                } catch {
                  setError("Invalid JSON");
                }
              }}
              disabled={!draft || save.isPending}
            >
              Save as new version
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
