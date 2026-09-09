import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EquityChart } from "../charts";
import { deltaClass, fmtMoney, fmtRate, shortHash } from "../format";

export function RunView({ id, onCompare }: { id: string; onCompare: (runId: string) => void }) {
  const run = useQuery({ queryKey: ["run", id], queryFn: () => api.run(id) });
  if (run.isLoading) return <p>Loading…</p>;
  if (run.isError) return <p className="error">Failed to load run.</p>;
  const r = run.data!.run;
  const m = r.metrics;
  const trades = Array.isArray(r.trades) ? r.trades : [];
  const warnings = Object.entries(r.warnings).filter(([, v]) => v !== 0 && v !== false);

  return (
    <div>
      <h2>
        Run <code>{shortHash(r.resultHash)}</code> <span className="muted">{r.engineVersion}</span>
      </h2>
      <p className="banner">
        Historical simulation ≠ future performance. MaxDD and Sharpe are in-sample descriptions, not guarantees.
      </p>
      <div className="cards">
        <Metric label="Net P&L" value={fmtMoney(m.netProfit)} n={m.tradeCount} />
        <Metric label="Return" value={m.totalReturnPct === null ? "—" : `${m.totalReturnPct.toFixed(2)}%`} n={m.tradeCount} />
        <Metric label="Win rate" value={m.winRate === null ? "—" : `${(m.winRate * 100).toFixed(1)}%`} n={m.tradeCount} />
        <Metric label="Profit factor" value={fmtRate(m.profitFactor)} n={m.tradeCount} />
        <Metric label="Expectancy" value={fmtMoney(m.expectancy)} n={m.tradeCount} />
        <Metric label="Max DD" value={`${fmtMoney(m.maxDrawdown)} (${m.maxDrawdownPct.toFixed(2)}%)`} n={m.tradeCount} />
        <Metric label="Sharpe" value={fmtRate(m.sharpe)} n={m.tradeCount} />
        <Metric label="Trades" value={String(m.tradeCount)} n={m.tradeCount} />
      </div>
      <EquityChart curve={r.equityCurve} />
      <h3>Assumptions &amp; warnings</h3>
      <ul>
        {r.assumptions.map((a) => (
          <li key={a}>{a}</li>
        ))}
        {warnings.map(([k, v]) => (
          <li key={k}>
            <strong>{k}</strong>: {String(v)}
          </li>
        ))}
      </ul>
      <h3>Trades ({Array.isArray(r.trades) ? trades.length : (r.trades as { total: number }).total})</h3>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Side</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>Net</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={t.id}>
              <td>{i + 1}</td>
              <td>{t.direction}</td>
              <td>{t.qty}</td>
              <td>{t.entryPrice}</td>
              <td>{t.exitPrice}</td>
              <td className={deltaClass(Number(t.netPnl))}>{fmtMoney(t.netPnl)}</td>
              <td>
                {t.exitReason}
                {t.ambiguous ? " (ambiguous)" : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="link" onClick={() => onCompare(r.id)}>
        Compare this run →
      </button>
    </div>
  );
}

function Metric({ label, value, n }: { label: string; value: string; n: number }) {
  return (
    <div className="metric">
      <small className="muted">
        {label} · n={n}
      </small>
      <strong>{value}</strong>
    </div>
  );
}
