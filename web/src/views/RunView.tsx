import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EquityChart, PriceChart } from "../charts";
import { MonthlyHeatmap } from "../components/MonthlyHeatmap";
import { deltaClass, fmtMoney, fmtRate, shortHash } from "../format";

export function RunView({ id, onCompare }: { id: string; onCompare: (runId: string) => void }) {
  const run = useQuery({ queryKey: ["run", id], queryFn: () => api.run(id) });
  const [selectedTrade, setSelectedTrade] = useState<string | null>(null);

  const datasetId = run.data?.run.datasetId;
  const config = run.data?.run.config as { startTime?: number; endTime?: number } | undefined;
  const bars = useQuery({
    queryKey: ["run-bars", id],
    queryFn: () => api.datasetBars(datasetId!, Number(config?.startTime ?? 0), Number(config?.endTime ?? 0)),
    enabled: !!datasetId && !!config,
  });

  if (run.isLoading) return <p>Loading…</p>;
  if (run.isError) return <p className="error">Failed to load run.</p>;
  const r = run.data!.run;
  const m = r.metrics as unknown as Record<string, string | number | null> & {
    monthly?: { period: string; netPnl: string; trades: number }[];
  };
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
      <div className="grid cards-4">
        <Metric label="Net P&L" value={fmtMoney(m.netProfit as string)} n={Number(m.tradeCount)} strong />
        <Metric label="Return" value={m.totalReturnPct === null ? "—" : `${Number(m.totalReturnPct).toFixed(2)}%`} n={Number(m.tradeCount)} />
        <Metric label="Win rate" value={m.winRate === null ? "—" : `${(Number(m.winRate) * 100).toFixed(1)}%`} n={Number(m.tradeCount)} />
        <Metric label="Profit factor" value={fmtRate(m.profitFactor as number | null)} n={Number(m.tradeCount)} />
        <Metric label="Expectancy" value={fmtMoney(m.expectancy as string)} n={Number(m.tradeCount)} />
        <Metric label="Max DD" value={`${fmtMoney(m.maxDrawdown as string)} (${Number(m.maxDrawdownPct).toFixed(2)}%)`} n={Number(m.tradeCount)} />
        <Metric label="Sharpe" value={fmtRate(m.sharpe as number | null)} n={Number(m.tradeCount)} />
        <Metric label="Trades" value={String(m.tradeCount)} n={Number(m.tradeCount)} />
      </div>

      <div className="chart-wrap">
        <h4>Price + trades {bars.data?.downsampled ? <span className="muted">(downsampled {bars.data.total} → shown)</span> : null}</h4>
        {bars.isLoading && <p className="muted">Loading candles…</p>}
        {bars.data && <PriceChart bars={bars.data.bars} trades={trades} />}
      </div>

      <div className="chart-wrap">
        <h4>Equity (blue) + drawdown (red, lower pane scale)</h4>
        <EquityChart curve={r.equityCurve} />
      </div>

      <MonthlyHeatmap buckets={(m.monthly as { period: string; netPnl: string; trades: number }[] | undefined) ?? []} label="Monthly P&L" />

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
            <tr key={t.id} className={selectedTrade === t.id ? "selected" : ""} onClick={() => setSelectedTrade(t.id)} style={{ cursor: "pointer" }}>
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

function Metric({ label, value, n, strong }: { label: string; value: string; n: number; strong?: boolean }) {
  return (
    <div className="card metric">
      <small className="muted">
        {label} · n={n}
      </small>
      <strong style={strong ? { fontSize: "1.4rem" } : undefined}>{value}</strong>
    </div>
  );
}
