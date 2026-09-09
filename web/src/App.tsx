import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AiPanel } from "./views/AiPanel";
import { Compare } from "./views/Compare";
import { Launcher } from "./views/Launcher";
import { RunView } from "./views/RunView";
import { Strategies } from "./views/Strategies";
import { StrategyDetail } from "./views/StrategyDetail";

const client = new QueryClient();

type View =
  | { name: "strategies" }
  | { name: "strategy"; id: string }
  | { name: "launcher"; versionId: string | null }
  | { name: "run"; id: string }
  | { name: "compare"; seed: string | null }
  | { name: "ai"; versionId: string | null; runIds: string[] };

export function App() {
  const [view, setView] = useState<View>({ name: "strategies" });
  return (
    <QueryClientProvider client={client}>
      <div className="app">
        <nav>
          <strong>AlphaLab</strong>
          <button className="link" onClick={() => setView({ name: "strategies" })}>
            Strategies
          </button>
          <button className="link" onClick={() => setView({ name: "launcher", versionId: null })}>
            Backtest
          </button>
          <button className="link" onClick={() => setView({ name: "compare", seed: null })}>
            Compare
          </button>
          <button className="link" onClick={() => setView({ name: "ai", versionId: null, runIds: [] })}>
            AI
          </button>
        </nav>
        <main>
          {view.name === "strategies" && <Strategies onOpen={(id) => setView({ name: "strategy", id })} />}
          {view.name === "strategy" && (
            <StrategyDetail id={view.id} onBacktest={(versionId) => setView({ name: "launcher", versionId })} />
          )}
          {view.name === "launcher" && (
            <Launcher presetVersionId={view.versionId} onDone={(id) => setView({ name: "run", id })} />
          )}
          {view.name === "run" && (
            <RunView id={view.id} onCompare={(runId) => setView({ name: "compare", seed: runId })} />
          )}
          {view.name === "compare" && <Compare seedRunId={view.seed} />}
          {view.name === "ai" && <AiPanel versionId={view.versionId} runIds={view.runIds} />}
        </main>
      </div>
    </QueryClientProvider>
  );
}
