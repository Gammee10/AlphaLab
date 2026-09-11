import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type RunSummary } from "../api";
import { deltaClass, fmtMoney, shortHash } from "../format";
import { navigate } from "../router";
import { useUi } from "../store";
import {
  Badge,
  EmptyState,
  ErrorInline,
  Loading,
  PageHead,
  Skeleton,
} from "../components/ui";
import { IcCoin, IcDb, IcLayers, IcPlay, IcSearch, IcSpark } from "../components/icons";

type SortKey = "resultHash" | "tradeCount" | "netProfit" | "winRate" | "profitFactor" | "maxDrawdownPct";

function num(r: RunSummary, k: SortKey): number | null {
  if (k === "resultHash") return null;
  if (k === "netProfit") return r.netProfit === null ? null : Number(r.netProfit);
  return r[k] === null ? null : (r[k] as number);
}

export function Dashboard() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.runs(20) });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus });
  const { toast } = useUi();

  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "netProfit", dir: -1 });
  const [filter, setFilter] = useState("");

  const rows = useMemo(() => {
    const list = runs.data?.runs ?? [];
    const needle = filter.trim().toLowerCase();
    const filtered = needle ? list.filter((r) => r.resultHash.toLowerCase().includes(needle)) : list;
    const sorted = [...filtered].sort((a, b) => {
      const av = num(a, sort.key);
      const bv = num(b, sort.key);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av - bv) * sort.dir;
    });
    return sorted;
  }, [runs.data, filter, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: -1 }));

  const arrow = (key: SortKey) => (sort.key === key ? <span className="sort-arrow">{sort.dir === 1 ? "▲" : "▼"}</span> : null);

  return (
    <div>
      <PageHead
        eyebrow="Research overview"
        title="Research dashboard"
        sub="Live overview of your strategies, datasets and latest simulations."
        actions={
          <button className="btn primary" onClick={() => navigate("/launcher")}>
            <IcPlay size={14} />
            New backtest
          </button>
        }
      />

      <div className="stat-grid">
        <div className="glass stat-card">
          <div className="stat-icon">
            <IcLayers size={18} />
          </div>
          <div>
            <div className="stat-label">Strategies</div>
            <div className="stat-value">
              {strategies.data ? strategies.data.strategies.length : <Skeleton w={40} h={22} />}
            </div>
          </div>
        </div>
        <div className="glass stat-card">
          <div className="stat-icon tone-neutral">
            <IcDb size={18} />
          </div>
          <div>
            <div className="stat-label">Datasets</div>
            <div className="stat-value">
              {datasets.data ? datasets.data.datasets.length : <Skeleton w={40} h={22} />}
            </div>
          </div>
        </div>
        <div className="glass stat-card">
          <div className="stat-icon tone-neutral">
            <IcCoin size={18} />
          </div>
          <div>
            <div className="stat-label">Backtests</div>
            <div className="stat-value">
              {runs.data ? runs.data.runs.length : <Skeleton w={40} h={22} />}
            </div>
            <div className="stat-sub">latest 20</div>
          </div>
        </div>
        <div className="glass stat-card">
          <div className="stat-icon tone-up">
            <IcSpark size={18} />
          </div>
          <div>
            <div className="stat-label">AI assistant</div>
            <div className="stat-value" style={{ fontSize: "1.05rem" }}>
              {ai.data ? (ai.data.keyConfigured ? `gemini (${ai.data.provider})` : "ruled") : <Skeleton w={80} h={18} />}
            </div>
            <div className="stat-sub">{ai.data && !ai.data.keyConfigured ? "offline rule-based fallback" : "\u00a0"}</div>
          </div>
        </div>
      </div>

      <div className="glass" style={{ padding: 0, overflow: "hidden", marginTop: "1.6rem" }}>
        <div className="card-head" style={{ padding: "0.9rem 0.95rem 0", marginBottom: 0 }}>
          <span className="card-icon">
            <IcPlay size={14} />
          </span>
          <span className="card-title">Recent backtests</span>
          <span className="card-right">
            {runs.data && <span className="faint" style={{ fontSize: "0.76rem" }}>{runs.data.runs.length} runs</span>}
          </span>
        </div>
        <div className="filter-bar">
          <IcSearch size={14} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by run hash…"
            style={{ maxWidth: 280 }}
          />
          <div className="grow" />
          <button
            className="btn glass sm"
            onClick={() => {
              setFilter("");
              setSort({ key: "netProfit", dir: -1 });
              toast("Table reset", "info");
            }}
          >
            Reset
          </button>
        </div>

        {runs.isLoading ? (
          <div style={{ padding: "1rem" }}>
            <Loading text="Loading runs…" />
          </div>
        ) : runs.isError ? (
          <div style={{ padding: "1rem" }}>
            <ErrorInline text="Failed to load runs — is the API running?" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="No backtests yet"
            children="Create a strategy, then launch your first backtest from the Backtest tab."
            action={
              <button className="btn primary sm" onClick={() => navigate("/strategies")}>
                <IcLayers size={14} />
                Browse strategies
              </button>
            }
          />
        ) : (
          <table>
            <thead>
              <tr>
                <th className="sortable" onClick={() => toggleSort("resultHash")}>
                  Run {arrow("resultHash")}
                </th>
                <th>Status</th>
                <th className="sortable" onClick={() => toggleSort("tradeCount")}>
                  Trades {arrow("tradeCount")}
                </th>
                <th className="sortable" onClick={() => toggleSort("netProfit")}>
                  Net {arrow("netProfit")}
                </th>
                <th className="sortable" onClick={() => toggleSort("winRate")}>
                  Win rate {arrow("winRate")}
                </th>
                <th className="sortable" onClick={() => toggleSort("profitFactor")}>
                  PF {arrow("profitFactor")}
                </th>
                <th className="sortable" onClick={() => toggleSort("maxDrawdownPct")}>
                  MaxDD% {arrow("maxDrawdownPct")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const net = r.netProfit === null ? null : Number(r.netProfit);
                const done = r.profitFactor !== null;
                return (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/run/${r.id}`)}>
                    <td>
                      <code>{shortHash(r.resultHash)}</code>
                    </td>
                    <td>{done ? <Badge kind="ok">done</Badge> : <Badge kind="warn">in-flight</Badge>}</td>
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
