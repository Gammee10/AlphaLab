# Backtest engine (normative execution semantics)

Engine version: `engine/1.0`. Any semantic change → bump version; old runs stay valid under their recorded version.
Location: `backend/alphalab_core` (pure Python: stdlib + numpy kernels only, no FastAPI/SQLAlchemy/HTTP/AI imports). Signature: `run_backtest(spec, bars, config) -> BacktestRunPayload`.

## 1. Timing contract (anti-lookahead)

1. Bars sorted ascending by `openTime`; duplicates/invalid rejected at import (see `docs/market-data.md`), never silently reordered at run time (misorder → `DATA_NOT_ORDERED` failure).
2. Indicators at bar index `t` consume only bars `0..t` (closed-bar values). Any operand with `offsetBars: k` reads state at `t-k`.
3. Signals evaluated **after bar `t` closes**. Earliest fill: **open of bar `t+1`**.
4. Stops/targets attached at fill bar `f` are first checkable on bar `f`'s own range **excluding the fill tick** (conservative: entry at open, then `high/low` of same bar may stop you out) and every bar thereafter.
5. Session/volatility/spread filters evaluated on bar `t` (signal bar) using `t`-available data only.
6. Warmup: while any referenced indicator is `warmingUp`, signals suppressed (counted in `warnings.warmupBarsSkipped`).
7. Cold-start lookback (anti-truncation rule): the engine never seeds indicators from the run's `startTime` directly. The API must supply bars over `[startTime − lookbackWindow, endTime]`, where `lookbackWindow` covers `warmupBars = max(3 × maxIndicatorPeriod, 50)` bars back in the same dataset (clamped to dataset start). Indicator state is computed across the lookback; only bars with `openTime ≥ startTime` may generate signals or fills. If fewer than `warmupBars` pre-bars exist (dataset starts near `startTime`), the run proceeds with `warnings.coldStart: true` and the deficit count — visible in the UI, never silent. `crossesAbove/Below` additionally require bars `t` and `t−1` both non-warmup, else no signal.

Pseudocode per bar (after close of `t`):

```text
state.indicators.update(bars[t])            # uses ≤ t only
if warmingUp(any referenced): mark, continue
signal = evalEntry(spec, t) && evalFilters(spec, t)   # booleans, closed data
pending = signal ? {direction, stopDist from ATR[t]/pips} : none   # stored for t+1
# execution of pending-from-(t-1) and open-position stops happens on bars[t] open/high/low (see §2–3)
```

## 2. Order and fill model (MVP subset)

Supported: **market entry at next open** + **attached SL/TP** (+ optional trailing / time-stop / opposite-signal exit). One position max per run.

On bar `t+1` with pending entry from signal bar `t`:

- `rawFill = open[t+1]`.
- Entry side adjustment: long pays ask (`open + spread/2`), short receives bid (`open − spread/2`), where `spread = config.costs.spreadBps × price / 10_000`.
- Slippage: `fill ± slippageBps` applied **adversely** (long higher, short lower). Slippage model `bps` in MVP (an `atr` option is schema-reserved, rejected in v1).
- Commission: `commissionPerUnit × qty` charged on entry and on exit.
- Capital check: required margin estimate `notional / leverageMax`; if `notional > equity × maxNotionalMult` or insufficient cash → entry **skipped** with `warnings.capitalSkips++` (never silently downsized — downsizing hides risk; skip-and-disclose).
- Gaps: if `open[t+1]` is beyond the stop on the entry bar itself (gap-through-stop), fill at `open[t+1]` and stop triggers same bar at `open[t+1]`-adverse side (worst realistic, disclosed).
- Pending-while-open: with one position open, a same-direction pending entry is **ignored** (`warnings.pyramidSkips++`); an opposite-direction pending entry first **closes** the open position at `open[t+1]` (exit leg, own commission) and then **opens** the new position at the same `open[t+1]` (entry leg, own commission) — a documented two-leg reversal, never a netted single fill.
- Order lifecycle (every pending signal produces exactly one terminal `Order` row): `pending → filled | skipped_capital | skipped_min_qty | ignored_pyramid | expired_end_of_data`. Skipped/ignored orders are stored (not dropped) so "why only 40 trades?" is answerable.

Unsupported in v1 (reject at validation, `NOT_SUPPORTED_IN_MVP`): limit/stop entries, partials, pyramiding/adds, concurrent positions, bracket-replacement mid-trade.

## 3. Stop / target checking (intrabar ambiguity — pessimistic)

For an open long with `stop S < entry E < target T`, on each bar with range `[L, H]` (after entry bar's fill):

- If `L ≤ S` and `H ≥ T` (both touched): **stop first** (pessimistic). Record `warnings.ambiguousBars++`.
- Else if `L ≤ S`: stop fill at `S` with exit-side costs (long: `S − spread/2 − slippage`; short: `S + spread/2 + slippage`).
- Else if `H ≥ T`: target fill at `T` with exit-side costs (long: `T − spread/2 − slippage`; short: `T + spread/2 + slippage`).
- Trailing (normative): once unrealized profit reaches `activationR` (in units of initial stop distance R; default 1.0 if omitted), `S` ratchets each bar to `max(S, highestFavorable − atrMultiplier × ATR[t])` for longs (mirror for shorts); it never loosens. Trailing exits use exit-side costs and `exitReason: trailing`.
- Time-stop: close at `open` of bar `entryBar + N` if still open.
- Opposite-signal exit: evaluated on close `t`; executed at open `t+1` (same next-open rule, not intrabar).
- Exact-touch fills: touching `S`/`T` exactly (`L == S`, `H == T`) **counts as hit** (boundary tests required).

Shorts mirror. All fills subtract spread/slippage/commission; every trade stores `entryBar, exitBar, entryPrice, exitPrice, qty, fees, grossPnl, netPnl, exitReason {stop|target|trailing|time|opposite|end-of-data}, ambiguous?: bool`.

End-of-data: open position force-closed at last close (reason `end-of-data`, flagged so users don't mistake truncation for alpha).

## 4. Position sizing

```text
stopDistance = |entryEstimate − stopPrice|      # entryEstimate = signal-bar close ± spread/2 (ESTIMATE, not fill)
riskCash     = equityBeforeTrade × riskPerTradePct / 100   # equityBeforeTrade == cash (≤1 position ⇒ no unrealized component)
qtyRaw       = riskCash / stopDistance
qty          = floor(qtyRaw to instrument lot step)  # steps from versioned instrument metadata (see docs/persistence.md)
qty capped so notional ≤ equity × maxNotionalMult; if qty < minimum → skip (warnings.minQtySkips++)
```

**Estimate-vs-fill disclosure (adversarial finding, now explicit):** quantity is computed from the signal-bar-close estimate, but the fill happens at next open — on gaps the realized risk differs from intended risk. The engine stores both `intendedRiskCash` and `realizedRiskCash = qty × |fillPrice − stopPrice|` per trade, and sets `warnings.gapRiskExceeded` when realized exceeds intended by > 20%. It never re-sizes at fill time (that would be its own lookahead-flavored distortion: the quantity decision belongs to the signal moment).

No volatility-targeting, no Kelly, no compounding switch in v1 — `riskPerTradePct` on current equity is the only compounding mechanism (documented so curves are interpretable).

## 5. Equity, fees, corporate specifics

- `equity[t] = cash + positionQty × (close[t] − avgEntry) × direction − accruedCosts`. Marked to **close** every bar; `cash` only moves on fills.
- FX/XAU/BTC spot MVP: no expiry, no dividends, no funding; leverage is a cap, not a margin-call simulator (a `marginCallSimulated: false` flag is stored so nobody mistakes backtest leverage for broker margin behavior).
- Dead-bar / zero-range / missing-bar behavior: no signals on absent bars; indicators **pause** (do not forward-fill prices); gap recorded in run warnings with bar counts.

## 6. Costs configuration (per run, part of identity)

```text
costs: { spreadBps: number;      // e.g. EURUSD 15, XAUUSD 25, BTCUSD 5
         slippageBps: number;    // default 5; 0 allowed for sensitivity runs
         commissionPerUnit: number } // default 0 for FX/CFD, exchange fee for BTC
```

Presets per symbol documented in `docs/market-data.md`; every run stores the actual values used — no global mutable cost table that could rewrite history.

## 7. Determinism

- Pure function; float ops in fixed order; no iteration over unordered maps.
- `resultHash = sha256(canonical(specHash, datasetHash, configHash, engineVersion, instrumentMetaVersion, trades[]))`.
- Required test: run same fixture twice → identical hash; run with `slippageBps: 0` vs `5` → different hash (sensitivity proof).
- Host-independence: identical inputs produce identical outputs regardless of thread/process/executor — the engine reads nothing from ambient state, so moving it to a worker process cannot change results (verified by the cross-host determinism test running the same fixture in-process and in a spawned subprocess).

## 8. Worked micro-example (for engine tests)

Bars (closes): `100, 101, 102, 103`; signal long after close of bar 2 (index 1); `open[2] = 102`; spread 0, slippage 0, commission 0; stop 1.0 below entry, target 2.0 above; risk sizes qty = 10.

- Entry fill 102 at open of bar 2. Stop 101, target 104.
- Bar 2 range H/L = 103/101 → `L == S` → stop hit. Exit 101.
- `gross = (101−102)×10 = −10`, net −10. One trade, `exitReason: stop`, `ambiguous: false`.

A second fixture with `H=104, L=100` on the exit bar must produce a **stop** exit (pessimistic ordering) — this is the ambiguity test.

## 9. Why v1 is narrow — and why it is not a bottleneck (read before extending)

v1 deliberately supports one open position, market entries at next open, and attached SL/TP (+ trailing/time/opposite). This reads as narrow, so here is the explicit case that it is the right narrow and the extension path is real, not aspirational:

**Why this narrow covers evaluation.** The four MVP templates (trend-pullback, Donchian breakout, Bollinger mean-reversion, RSI momentum) all express fully under v1 semantics. The research questions in the brief that determine "does this have an edge" — trend vs filter, stop-distance sweeps, session filters, timeframe/market/period comparison — are all answerable. What v1 cannot yet express (partials, scale-ins, limit/stop entries, concurrent positions) changes *position management sophistication*, not the ability to judge whether the entry logic has merit. Shipping those half-correctly would poison the very comparisons the product exists to make.

**Why it doesn't block scaling (extension seams, not promises).** The pipeline is staged as `signals → pending orders → fills → position ledger → equity`, with each stage a pure function over the event stream:
- `Order` already carries `kind` (`market` in v1; `limit/stop` reserved) and `Position` carries `legs[]` (length 1 in v1) — `engine/2.0` adds kinds/legs without changing stored v1 runs.
- `reservedForFuture` fields are versioned extension points: v1 validates-and-rejects; v2 activates them behind `engineVersion` bump, so old result hashes never change meaning.
- The ledger is per-position, not global-integer: allowing N positions is a cap change + matching-rule addition (FIFO vs LIFO disclosed), not a rewrite.
- Partial exits reuse the existing `fees/gross/net` per-fill accounting (each partial is a fill event against the same position id).
So growth is additive capabilities under a new engine version with the same determinism/hash contract — the measured risk is sequencing (build v2 only after v1 fixtures are green), not architecture.

## 10. Execution host (normative — where the engine runs)

The engine is CPU-bound pure Python (a 200k-bar run is seconds of GIL-held compute). Running it on the asyncio event loop would freeze SSE, every HTTP endpoint, and other jobs — so:

- **Sync path (`< 200k` bars):** handler is a **sync `def`** route → FastAPI runs it in its threadpool; the event loop is never blocked. Bound: still capped at 200k bars so worst-case threadpool holdout stays ~seconds.
- **Async path (`≥ 200k` bars):** the job runner dispatches the engine to a **`ProcessPoolExecutor(max_workers=2)`** (true parallelism for the concurrency-2 queue; GIL no longer serializes jobs). `alphalab_core` must be import-safe under spawn (no side effects at import). The worker receives `(spec, bars, config)` as plain data and returns the run payload — no shared state, so determinism is structural.
- **Cancel:** the cancel flag lives in the **DB** (`backtest_jobs.state` / a `cancel_requested` column); the worker polls it every 1,000 bars and terminates cooperatively. An in-memory flag would not cross the process boundary.
- **Timeout (120s):** enforced by the runner killing the worker task/process; the run-row write is transactional (see `docs/api.md`), so a killed worker leaves zero partial rows.
- **Results return** to the event loop for the single transactional DB write + SSE completion event.

This is the "10× workload" answer: 10× bars = slower runs, same semantics; 100× = the queue's backpressure (`429`) engages; 1000× = the documented arq/worker extraction seam, not a redesign.
