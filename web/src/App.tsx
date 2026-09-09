import { useState } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { AiPanel } from "./views/AiPanel";
import { Compare } from "./views/Compare";
import { Dashboard } from "./views/Dashboard";
import { Launcher } from "./views/Launcher";
import { RunView } from "./views/RunView";
import { Strategies } from "./views/Strategies";
import { StrategyDetail } from "./views/StrategyDetail";

const client = new QueryClient();

type View =
  | { name: "dashboard" }
  | { name: "strategies" }
  | { name: "strategy"; id: string }
  | { name: "launcher"; versionId: string | null }
  | { name: "run"; id: string }
  | { name: "compare"; seed: string | null }
  | { name: "ai"; versionId: string | null; runIds: string[] };

const NAV: { name: View["name"]; label: string }[] = [
  { name: "dashboard", label: "◈ Desk" },
  { name: "strategies", label: "◐ Strategies" },
  { name: "launcher", label: "▶ Backtest" },
  { name: "compare", label: "⇄ Compare" },
  { name: "ai", label: "✦ AI" },
];

function Status() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => fetch("/api/health").then((r) => r.json()), refetchInterval: 15000 });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, refetchInterval: 60000 });
  const ok = health.data?.ok === true;
  return (
    <div className="status">
      <div>
        <span className={`dot ${ok ? "ok" : "off"}`} />
        API {ok ? "connected" : "down"}
      </div>
      <div className="muted">AI: {ai.data ? (ai.data.keyConfigured ? `gemini (${ai.data.provider})` : "ruled · offline") : "…"}</div>
    </div>
  );
}

export function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });
  const go = (v: View) => setView(v);
  return (
    <QueryClientProvider client={client}>
      <div className="shell">
        <nav className="sidebar">
          <div className="brand">
            Alpha<span>Lab</span>
          </div>
          {NAV.map((n) => (
            <button
              key={n.name}
              className={view.name === n.name || (n.name === "strategies" && view.name === "strategy") ? "nav active" : "nav"}
              onClick={() => {
                if (n.name === "launcher") go({ name: "launcher", versionId: null });
                else if (n.name === "compare") go({ name: "compare", seed: null });
                else if (n.name === "ai") go({ name: "ai", versionId: null, runIds: [] });
                else go({ name: n.name } as View);
              }}
            >
              {n.label}
            </button>
          ))}
          <Status />
        </nav>
        <main className="content">
          {view.name === "dashboard" && <Dashboard go={(v) => v.name === "run" && v.id && go({ name: "run", id: v.id })} />}
          {view.name === "strategies" && <Strategies onOpen={(id) => go({ name: "strategy", id })} />}
          {view.name === "strategy" && (
            <StrategyDetail id={view.id} onBacktest={(versionId) => go({ name: "launcher", versionId })} />
          )}
          {view.name === "launcher" && (
            <Launcher presetVersionId={view.versionId} onDone={(id) => go({ name: "run", id })} />
          )}
          {view.name === "run" && <RunView id={view.id} onCompare={(runId) => go({ name: "compare", seed: runId })} />}
          {view.name === "compare" && <Compare seedRunId={view.seed} onOpenRun={(id) => go({ name: "run", id })} />}
          {view.name === "ai" && <AiPanel versionId={view.versionId} runIds={view.runIds} />}
        </main>
      </div>
    </QueryClientProvider>
  );
}
