import { useState } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { IconChart, IconCompare, IconLayers, IconPlay, IconSpark } from "./components/ui";
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

const GROUPS: { label: string; items: { name: View["name"]; label: string; ico: (props: { size?: number }) => JSX.Element }[] }[] = [
  {
    label: "Research",
    items: [
      { name: "dashboard", label: "Desk", ico: IconChart },
      { name: "strategies", label: "Strategies", ico: IconLayers },
    ],
  },
  {
    label: "Work",
    items: [
      { name: "launcher", label: "Backtest", ico: IconPlay },
      { name: "compare", label: "Compare", ico: IconCompare },
    ],
  },
  {
    label: "Assist",
    items: [{ name: "ai", label: "AI copilot", ico: IconSpark }],
  },
];

function Status() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/api/health").then((r) => r.json()),
    refetchInterval: 15000,
  });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, refetchInterval: 60000 });
  const ok = health.data?.ok === true;
  return (
    <div className="sidebar-footer">
      <div className="status-row">
        <span className={`status-dot ${ok ? "ok" : "off"}`} />
        API {ok ? "connected" : "down"}
      </div>
      <div className="status-row">
        <span className="status-dot off" style={{ background: "transparent", boxShadow: "none" }} />
        AI: {ai.data ? (ai.data.keyConfigured ? `gemini (${ai.data.provider})` : "ruled · offline") : "…"}
      </div>
    </div>
  );
}

export function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });
  const go = (v: View) => setView(v);
  const isActive = (name: View["name"]) =>
    view.name === name || (name === "strategies" && view.name === "strategy");
  return (
    <QueryClientProvider client={client}>
      <div className="shell">
        <nav className="sidebar">
          <div className="brand">
            <div className="brand-mark">
              <IconChart size={18} />
            </div>
            <div className="brand-name">
              Alpha<em>Lab</em>
            </div>
          </div>
          {GROUPS.map((g) => (
            <div key={g.label}>
              <div className="nav-label">{g.label}</div>
              {g.items.map((n) => (
                <button
                  key={n.name}
                  className={isActive(n.name) ? "nav-item active" : "nav-item"}
                  onClick={() => {
                    if (n.name === "launcher") go({ name: "launcher", versionId: null });
                    else if (n.name === "compare") go({ name: "compare", seed: null });
                    else if (n.name === "ai") go({ name: "ai", versionId: null, runIds: [] });
                    else go({ name: n.name } as View);
                  }}
                >
                  <n.ico size={16} />
                  {n.label}
                </button>
              ))}
            </div>
          ))}
          <Status />
        </nav>
        <main className="content view-fade" key={view.name + (view.name === "run" ? view.id : "")}>
          {view.name === "dashboard" && <Dashboard go={(v) => v.name === "run" && v.id && go({ name: "run", id: v.id })} />}
          {view.name === "strategies" && <Strategies onOpen={(id) => go({ name: "strategy", id })} />}
          {view.name === "strategy" && (
            <StrategyDetail id={view.id} onBacktest={(versionId) => go({ name: "launcher", versionId })} />
          )}
          {view.name === "launcher" && <Launcher presetVersionId={view.versionId} onDone={(id) => go({ name: "run", id })} />}
          {view.name === "run" && <RunView id={view.id} onCompare={(runId) => go({ name: "compare", seed: runId })} />}
          {view.name === "compare" && <Compare seedRunId={view.seed} onOpenRun={(id) => go({ name: "run", id })} />}
          {view.name === "ai" && <AiPanel versionId={view.versionId} runIds={view.runIds} />}
        </main>
      </div>
    </QueryClientProvider>
  );
}
