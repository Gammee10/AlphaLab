import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { deltaClass, fmtMoney, shortHash } from "../format";

export function Dashboard({ go }: { go: (v: { name: string; id?: string }) => void }) {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.runs(10) });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus });

  return (
    <div>
      <h2>Research desk</h2>
      <div className="grid cards-4">
        <div className="card metric">
          <small className="muted">Strategies</small>
          <strong>{strategies.data?.strategies.length ?? "…"}</strong>
        </div>
        <div className="card metric">
          <small className="muted">Datasets</small>
          <strong>{datasets.data?.datasets.length ?? "…"}</strong>
        </div>
        <div className="card metric">
          <small className="muted">Backtests</small>
          <strong>{runs.data?.runs.length ?? "…"}</strong>
        </div>
        <div className="card metric">
          <small className="muted">AI</small>
          <strong>{ai.data ? (ai.data.keyConfigured ? `gemini (${ai.data.provider})` : "ruled (offline)") : "…"}</strong>
        </div>
      </div>
      <h3>Recent backtests</h3>
      {runs.data && runs.data.runs.length === 0 && (
        <p className="muted">No runs yet — create a strategy, then run your first backtest.</p>
      )}
      <table>
        <thead>
          <tr>
            <th>Run</th>
            <th>Trades</th>
            <th>Net</th>
            <th>Win rate</th>
            <th>PF</th>
            <th>MaxDD%</th>
          </tr>
        </thead>
        <tbody>
          {(runs.data?.runs ?? []).map((r) => (
            <tr key={r.id}>
              <td>
                <button className="link" onClick={() => go({ name: "run", id: r.id })}>
                  <code>{shortHash(r.resultHash)}</code>
                </button>
              </td>
              <td>{r.tradeCount ?? "—"}</td>
              <td className={deltaClass(r.netProfit === null ? null : Number(r.netProfit))}>
                {r.netProfit === null ? "—" : fmtMoney(r.netProfit)}
              </td>
              <td>{r.winRate === null ? "—" : `${(r.winRate * 100).toFixed(1)}%`}</td>
              <td>{r.profitFactor === null ? "—" : r.profitFactor.toFixed(2)}</td>
              <td>{r.maxDrawdownPct === null ? "—" : `${r.maxDrawdownPct.toFixed(2)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
