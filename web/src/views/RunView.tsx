import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EquityChart, PriceChart } from "../charts";
import { MonthlyHeatmap } from "../components/MonthlyHeatmap";
import { Badge, DirBadge, ErrorNotice, IconAlert, Loading, MetricCard, PageHead } from "../components/ui";
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

  if (run.isLoading) return <Loading text="Loading run…" />;
  if (run.isError) return <ErrorNotice message="Failed to load run." />;
  const r = run.data!.run;
  const m = r.metrics as unknown as Record<string, string | number | null> & {
    monthly?: { period: string; netPnl: string; trades: number }[];
  };
  const trades = Array.isArray(r.trades) ? r.trades : [];
  const warnings = Object.entries(r.warnings).filter(([, v]) => v !== 0 && v !== false);
  const net = Number(m.netProfit);

  return (
    <div>
      <PageHead
        title={
          <>
            Run <code>{shortHash(r.resultHash)}</code> <Badge kind="neutral">{r.engineVersion}</Badge>
          </>
        }
        sub="Historical simulation with stored assumptions. Same inputs → identical hash, every time."
      />
      <div className="banner warn">
        <IconAlert size={16} />
        <span>
          Historical simulation ≠ future performance. MaxDD and Sharpe are in-sample descriptions, not guarantees.
        </span>
      </div>

      <div className="metric-grid">
        <MetricCard label="Net P&L" value={fmtMoney(m.netProfit as string)} note={`n=${m.tradeCount}`} large className={deltaClass(net)} />
        <MetricCard label="Return" value={m.totalReturnPct === null ? "—" : `${Number(m.totalReturnPct).toFixed(2)}%`} />
        <MetricCard label="Win rate" value={m.winRate === null ? "—" : `${(Number(m.winRate) * 100).toFixed(1)}%`} />
        <MetricCard label="Profit factor" value={fmtRate(m.profitFactor as number | null)} />
        <MetricCard label="Expectancy" value={fmtMoney(m.expectancy as string)} />
        <MetricCard label="Max DD" value={`${fmtMoney(m.maxDrawdown as string)} (${Number(m.maxDrawdownPct).toFixed(2)}%)`} />
        <MetricCard label="Sharpe" value={fmtRate(m.sharpe as number | null)} />
        <MetricCard label="Trades" value={String(m.tradeCount)} />
      </div>

      <div className="chart-card card">
        <div className="chart-title">
          <span>Price + trades</span>
          {bars.data?.downsampled ? <span className="faint">downsampled {bars.data.total} → shown</span> : null}
        </div>
        {bars.isLoading && <Loading text="Loading candles…" />}
        {bars.data && <PriceChart bars={bars.data.bars} trades={trades} />}
      </div>

      <div className="chart-card card">
        <div className="chart-title">
          <span>Equity + drawdown</span>
          <span className="faint">equity (blue) · drawdown (red, lower pane)</span>
        </div>
        <EquityChart curve={r.equityCurve} />
      </div>

      <MonthlyHeatmap buckets={(m.monthly as { period: string; netPnl: string; trades: number }[] | undefined) ?? []} label="Monthly P&L" />

      <h3 className="section-title">Assumptions &amp; warnings</h3>
      <div className="card">
        <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
          {r.assumptions.map((a) => (
            <li key={a} className="muted" style={{ margin: "0.2rem 0" }}>
              {a}
            </li>
          ))}
          {warnings.map(([k, v]) => (
            <li key={k} style={{ margin: "0.2rem 0", display: "flex", gap: "0.4rem", alignItems: "center" }}>
              <IconAlert size={13} />
              <span>
                <strong>{k}</strong>: {String(v)}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <h3 className="section-title">Trades ({Array.isArray(r.trades) ? trades.length : (r.trades as { total: number }).total})</h3>
      <div className="card table-card">
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
              <tr
                key={t.id}
                className={selectedTrade === t.id ? "selected" : ""}
                onClick={() => setSelectedTrade(t.id)}
                style={{ cursor: "pointer" }}
              >
                <td>{i + 1}</td>
                <td>
                  <DirBadge direction={t.direction} />
                </td>
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
      </div>
      <div style={{ marginTop: "1rem" }}>
        <button className="btn ghost" onClick={() => onCompare(r.id)}>
          Compare this run →
        </button>
      </div>
    </div>
  );
}
