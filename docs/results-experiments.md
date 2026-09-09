# Results, metrics, experiments

All calculations in `backend/alphalab_core` (pure Python). Frontend renders stored values only.

## Run payload (stored, immutable)

```ts
type BacktestRun = {
  id, jobId, strategyVersionId, datasetId,
  specHash, datasetHash, configHash, resultHash, engineVersion,
  config: BacktestConfig,           // canonical, includes costs + capital + period
  trades: Trade[], orders: Order[], // full detail (MVP sizes are small; cap: 50k trades/run)
  equityCurve: EquityPoint[],       // downsampled to ≤ 2000 points for storage; full hash kept
  fullResolutionHash: string,
  metrics: Metrics,
  assumptionsText: string[],        // e.g. "Fills at next open +5bps slippage", "ambiguous bars: 3 (stop-first)"
  warnings: { warmupBarsSkipped, capitalSkips, ambiguousBars, gapsEncountered, minQtySkips },
  createdAt: number
};
```

## Metrics (normative formulas — implement exactly)

Let `net[i]` = net P&L of trade `i` (after spread/slippage/commission), `N` = trade count, `W`/`L` wins/losses, `C0` initial capital, `E[t]` equity series marked to close.

- `netProfit = Σ net[i]`; `totalReturnPct = netProfit / C0 × 100`
- `winRate = W / N` (N=0 → null, never 0/0 = 0)
- `avgWin = Σ(net[i]>0)/W`, `avgLoss = Σ(net[i]<0)/L` (signed; null if empty side)
- `profitFactor = grossProfit / |grossLoss|` (no losses → `+∞` stored as null + flag `noLosses: true`; never divide by zero)
- `expectancy = netProfit / N` (per-trade, in account currency)
- `maxDrawdown = max over t (peak[t] − E[t])`, `maxDrawdownPct = maxDD / peak × 100`; `avgDrawdown` = mean of closed-drawdown episodes (informational)
- `sharpe ≈ mean(periodicRet) / sd(periodicRet) × √periodsPerYear`, periodic = per-bar close-to-close simple returns on equity; `periodsPerYear` from timeframe table below; `riskFree = 0`; shown only when trade count N ≥ 30 AND bar count ≥ 100 AND sd > 0, else null + `insufficientData` flag (never show a Sharpe off 4 trades or a flat equity line where sd = 0 would explode the ratio)
- `streaks`: max consecutive wins/losses
- `periodic`: monthly buckets `{month, netPnl, trades, winRate}` and weekly buckets `{week, netPnl, trades, winRate}` (UTC calendar month / ISO week Monday-start; brief asks for both, same code path)
- `bySession` (MVP-lite): buckets by signal-bar hour (London/Asian/NY labels are display-only)
- `tradeDistribution`: deciles of `net[i]` + histogram bins (10) for the UI

Annualization constants (fixed table, not invented per run):

| TF | bars/year (crypto 24/7 basis; FX flagged approx) |
|---|---|
| M5 | 105120 |
| M15 | 35040 |
| H1 | 8760 |
| H4 | 2190 |
| D1 | 365 |

Because FX has weekend gaps, every Sharpe/Sortino display carries `approxAnnualized: true` + tooltip. No Sortino/Calmar in MVP (avoid metric zoo; add only with ADR).

Empty/single-trade runs: metrics present with nulls + `N` shown prominently; UI never renders "0% win rate" for N=0.

## Equity storage

Full-resolution equity hashed; stored curve downsampled (deterministic every-kth, ≤ 2000 points) + drawdown curve derived. Trade-level audit never downsampled. Hard cap: runs exceeding 50,000 trades fail with `TOO_MANY_TRADES` (suggest wider stops/longer TF) — prevents storage blowup from degenerate configs.

**Drawdown provenance (exact):** the stored drawdown curve is derived from the **stored (downsampled) equity**; the `metrics.maxDrawdown` number is computed from **full-resolution** equity inside the engine. The UI chart may therefore show a marginally shallower trough than the headline number on sparse runs; the run view labels this ("curve downsampled; maxDD computed full-resolution"). Authoritative number is always the metric, never the chart.

## Hash scope (exact)

`configHash` covers startTime/endTime/initialCapital/costs/instrumentMetaVersion/inSample/outOfSample labels. `datasetHash` is the full-dataset `barsHash` (period selection lives in configHash, so two periods over one dataset share datasetHash and differ in configHash). `resultHash = sha256(specHash + datasetHash + configHash + engineVersion + instrumentMetaVersion + canonicalTrades)`. `engineVersion` covers execution AND metric formulas.

## Experiments and comparison

- `Experiment { id, name, hypothesis?, runIds[2..32], baselineRunId?, createdAt }`.
- Comparison view (computed live from immutable runs, never stored as new truth):
  - Header: which spec params / costs / dataset / period **changed** (auto-diff of canonical configs) vs what stayed constant — the "don't hide material differences" rule.
  - Metric deltas vs baseline (Δ net, Δ PF, Δ maxDD, Δ N) with null-safety.
  - Overlaid equity curves (normalized to % from C0 so different capitals compare honestly).
- Parameter sweep (MVP): UI "sweep" creates ≤ 32 runs (e.g. `slAtr ∈ {0.5,1,1.5,2}` × datasets) grouped into an auto-named experiment. No optimizer, no walk-forward in MVP — but `BacktestConfig` already has `inSample/outOfSample` fields so WF slots in without migration (runskling: engine ignores them except labeling in v1).
