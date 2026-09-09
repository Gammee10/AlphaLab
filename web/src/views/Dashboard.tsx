import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { deltaClass, fmtMoney, shortHash } from "../format";
import { Badge, EmptyState, IconCoin, IconDatabase, IconLayers, IconSpark, PageHead, StatCard } from "../components/ui";

export function Dashboard({ go }: { go: (v: { name: string; id?: string }) => void }) {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.runs(10) });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus });

  return (
    <div>
      <PageHead
        title="Research desk"
        sub="Latest simulations, strategy health and dataset inventory at a glance."
      />
      <div className="stat-grid">
        <StatCard label="Strategies" value={strategies.data?.strategies.length != null ? String(strategies.data.strategies.length) : "…"} ico={<IconLayers size={18} />} />
        <StatCard label="Datasets" value={datasets.data?.datasets.length != null ? String(datasets.data.datasets.length) : "…"} ico={<IconDatabase size={18} />} />
        <StatCard label="Backtests (latest 10)" value={runs.data?.runs.length != null ? String(runs.data.runs.length) : "…"} ico={<IconCoin size={18} />} />
        <StatCard
          label="AI assistant"
          value={ai.data ? (ai.data.keyConfigured ? `gemini (${ai.data.provider})` : "ruled") : "…"}
          sub={ai.data && !ai.data.keyConfigured ? "offline rule-based fallback" : undefined}
          ico={<IconSpark size={18} />}
        />
      </div>

      <h3 className="section-title">Recent backtests</h3>
      <div className="card table-card">
        {runs.data && runs.data.runs.length === 0 ? (
          <EmptyState title="No runs yet">
            Create a strategy, then launch your first backtest from the Backtest tab.
          </EmptyState>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Trades</th>
                <th>Net</th>
                <th>Win rate</th>
                <th>PF</th>
                <th>MaxDD%</th>
              </tr>
            </thead>
            <tbody>
              {(runs.data?.runs ?? []).map((r) => {
                const net = r.netProfit === null ? null : Number(r.netProfit);
                return (
                  <tr key={r.id}>
                    <td>
                      <button className="link" onClick={() => go({ name: "run", id: r.id })}>
                        <code>{shortHash(r.resultHash)}</code>
                      </button>
                    </td>
                    <td>
                      {r.profitFactor === null ? <Badge kind="neutral">in-flight</Badge> : <Badge kind="ok">done</Badge>}
                    </td>
                    <td>{r.tradeCount ?? "—"}</td>
                    <td className={deltaClass(net)}>
                      {net === null ? "—" : `${net > 0 ? "+" : ""}${fmtMoney(r.netProfit)}`}
                    </td>
                    <td>{r.winRate === null ? "—" : `${(r.winRate * 100).toFixed(1)}%`}</td>
                    <td>{r.profitFactor === null ? "—" : r.profitFactor.toFixed(2)}</td>
                    <td>{r.maxDrawdownPct === null ? "—" : `${r.maxDrawdownPct.toFixed(2)}%`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
