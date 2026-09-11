import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Trade } from "../api";
import { navigate } from "../router";
import { deltaClass, fmtMoney, fmtRate, shortHash } from "../format";
import { EquityChart, PriceChart } from "../charts";
import { MonthlyHeatmap } from "../components/MonthlyHeatmap";
import {
  Badge,
  Banner,
  CopyChip,
  EmptyState,
  ErrorInline,
  Loading,
  MetricCard,
  PageHead,
  SectionLabel,
  SidePill,
  TabBar,
} from "../components/ui";
import { IcChart, IcList, IcShield, IcSwap } from "../components/icons";

const TABS = [
  { id: "overview", label: "Overview", icon: <IcChart size={14} /> },
  { id: "trades", label: "Trades", icon: <IcList size={14} /> },
  { id: "assumptions", label: "Assumptions", icon: <IcShield size={14} /> },
];

export function RunView({ id }: { id: string }) {
  const run = useQuery({ queryKey: ["run", id], queryFn: () => api.run(id), enabled: id !== "" });
  const [tab, setTab] = useState("overview");
  const [sideFilter, setSideFilter] = useState<"all" | "long" | "short">("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const datasetId = run.data?.run.datasetId;
  const config = run.data?.run.config as { startTime?: number; endTime?: number } | undefined;
  const bars = useQuery({
    queryKey: ["run-bars", id],
    queryFn: () => api.datasetBars(datasetId!, Number(config?.startTime ?? 0), Number(config?.endTime ?? 0)),
    enabled: !!datasetId && !!config && tab === "overview",
  });

  useEffect(() => setPage(0), [sideFilter, search]);

  const trades = useQuery({
    queryKey: ["run-trades", id, page],
    queryFn: async () => {
      const all = await api.runTrades(id, page);
      return all;
    },
    enabled: id !== "" && tab === "trades",
    placeholderData: (prev) => prev,
  });

  const tableTrades = useMemo(() => {
    const src = trades.data?.trades ?? [];
    const needle = search.trim().toLowerCase();
    return sideFilter === "all" && !needle
      ? src
      : src.filter(
          (t) =>
            (sideFilter === "all" || t.direction === sideFilter) &&
            (!needle ||
              t.id.toLowerCase().includes(needle) ||
              t.exitReason.toLowerCase().includes(needle) ||
              String(t.entryPrice).includes(needle)),
        );
  }, [trades.data, sideFilter, search]);

  if (id === "") return <ErrorInline text="No run id in the URL." />;
  if (run.isLoading) return <Loading text="Loading run…" />;
  if (run.isError) return <ErrorInline text="Failed to load run." />;

  const r = run.data!.run;
  const m = r.metrics as unknown as Record<string, string | number | null> & {
    monthly?: { period: string; netPnl: string; trades: number }[];
  };
  const chartTrades: Trade[] = Array.isArray(r.trades) ? r.trades : [];
  const warnings = Object.entries(r.warnings).filter(([, v]) => v !== 0 && v !== false);
  const net = Number(m.netProfit);

  const totalTrades = trades.data?.total ?? (Array.isArray(r.trades) ? chartTrades.length : null);
  const pageCount = totalTrades !== null ? Math.max(1, Math.ceil(totalTrades / 50)) : 1;

  return (
    <div>
      <PageHead
        eyebrow="Backtest result"
        title={
          <>
            Run <CopyChip text={r.resultHash} label={shortHash(r.resultHash)} /> <Badge kind="neutral">{r.engineVersion}</Badge>
          </>
        }
        sub="Deterministic simulation: same inputs → identical hash, every time."
        actions={
          <button className="btn glass" onClick={() => navigate(`/compare/${r.id}`)}>
            <IcSwap size={14} />
            Compare this run
          </button>
        }
      />

      <Banner kind="warn">
        Historical simulation ≠ future performance. MaxDD and Sharpe are in-sample descriptions, not guarantees.
      </Banner>

      <div className="metric-grid">
        <MetricCard label="Net P&L" value={`${net > 0 ? "+" : ""}${fmtMoney(m.netProfit as string)}`} note={`n=${m.tradeCount}`} large tone={net > 0 ? "up" : net < 0 ? "down" : null} />
        <MetricCard label="Return" value={m.totalReturnPct === null ? "—" : `${Number(m.totalReturnPct).toFixed(2)}%`} />
        <MetricCard label="Win rate" value={m.winRate === null ? "—" : `${(Number(m.winRate) * 100).toFixed(1)}%`} />
        <MetricCard label="Profit factor" value={fmtRate(m.profitFactor as number | null)} />
        <MetricCard label="Expectancy" value={fmtMoney(m.expectancy as string)} />
        <MetricCard label="Max DD" value={`${fmtMoney(m.maxDrawdown as string)} · ${Number(m.maxDrawdownPct).toFixed(2)}%`} />
        <MetricCard label="Sharpe" value={fmtRate(m.sharpe as number | null)} />
        <MetricCard label="Trades" value={String(m.tradeCount)} />
      </div>

      <div style={{ marginTop: "1.2rem" }}>
        <TabBar tabs={TABS} active={tab} onChange={(t) => setTab(t)} />
      </div>

      {tab === "overview" && (
        <>
          <div className="chart-panel glass">
            <div className="chart-head">
              <div className="chart-name">Price + trade markers</div>
              {bars.data?.downsampled && <span className="faint" style={{ fontSize: "0.75rem" }}>downsampled {bars.data.total} → shown</span>}
            </div>
            {bars.isLoading && <Loading text="Loading candles…" />}
            {bars.data && <PriceChart bars={bars.data.bars} trades={chartTrades} />}
          </div>

          <div className="chart-panel glass">
            <div className="chart-head">
              <div className="chart-name">Equity + drawdown</div>
              <span className="faint" style={{ fontSize: "0.75rem" }}>equity (mint) · drawdown (red, lower pane)</span>
            </div>
            <EquityChart curve={r.equityCurve} />
          </div>

          <SectionLabel>Monthly P&amp;L</SectionLabel>
          <MonthlyHeatmap buckets={(m.monthly as { period: string; netPnl: string; trades: number }[] | undefined) ?? []} />
        </>
      )}

      {tab === "trades" && (
        <div className="glass" style={{ padding: 0, overflow: "hidden" }}>
          <div className="filter-bar">
            <div className="row-wrap">
              {(["all", "long", "short"] as const).map((s) => (
                <button
                  key={s}
                  className={`mini-btn${sideFilter === s ? "" : ""}`}
                  style={sideFilter === s ? { color: "var(--accent)", borderColor: "var(--accent-border)", background: "var(--accent-soft)" } : undefined}
                  onClick={() => setSideFilter(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search id, price, reason…" style={{ maxWidth: 260 }} />
            <div className="grow" />
            {totalTrades !== null && <span className="faint" style={{ fontSize: "0.8rem" }}>{totalTrades} total</span>}
          </div>

          {trades.isLoading ? (
            <Loading text="Loading trades…" />
          ) : tableTrades.length === 0 ? (
            <EmptyState title="No trades match">Adjust the side filter or search text.</EmptyState>
          ) : (
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
                {tableTrades.map((t, i) => (
                  <tr key={t.id}>
                    <td>{page * 50 + i + 1}</td>
                    <td>
                      <SidePill direction={t.direction} />
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
          )}
          <div className="row-wrap" style={{ justifyContent: "flex-end", padding: "0.7rem 1rem", borderTop: "1px solid var(--border)" }}>
            <button className="btn glass sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
              ← Prev
            </button>
            <span className="faint" style={{ fontSize: "0.8rem" }}>
              page {page + 1} / {pageCount}
            </span>
            <button className="btn glass sm" disabled={page + 1 >= pageCount} onClick={() => setPage((p) => p + 1)}>
              Next →
            </button>
          </div>
        </div>
      )}

      {tab === "assumptions" && (
        <div className="glass">
          <SectionLabel>Recorded assumptions</SectionLabel>
          <ul style={{ margin: 0, paddingLeft: "1.3rem" }}>
            {r.assumptions.map((a) => (
              <li key={a} className="muted" style={{ margin: "0.3rem 0", fontSize: "0.9rem" }}>
                {a}
              </li>
            ))}
          </ul>
          {warnings.length > 0 && (
            <>
              <SectionLabel>Warnings</SectionLabel>
              <div className="stack">
                {warnings.map(([k, v]) => (
                  <Banner key={k} kind="warn">
                    <b style={{ color: "var(--amber)" }}>{k}</b>
                    <span>: {String(v)}</span>
                  </Banner>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
