# Strategy representation (StrategySpec v1)

Decision record: `docs/adr/0002-strategy-representation.md`, `0003-no-code-execution.md`.

## Decision: declarative JSON, no code execution

Strategies are **data**: a versioned JSON document (`StrategySpec`) validated against the canonical JSON Schema (`shared/schemas/strategy.spec.json`) — Pydantic v2 on the backend, Zod on the frontend, equivalence-tested — and executed by the deterministic engine. There is no DSL interpreter, no user-supplied JS, no `eval`. This is what makes AI modification safe (patches are schema-checked), versioning exact (hash the canonical JSON), and backtests reproducible.

Alternatives rejected: executable TS/Python strategy functions (unsafe with AI-generated code, hard to version/diff, sandbox burden); full expression DSL with scripting (overkill for MVP, larger attack surface).

## Spec shape (v1, authoritative field list)

```ts
type StrategySpec = {
  specVersion: "1.0";
  universe: { symbol: "EURUSD"|"GBPUSD"|"XAUUSD"|"BTCUSD"; timeframe: "M5"|"M15"|"H1"|"H4"|"D1" };
  indicators: IndicatorDef[];          // max 8 in MVP
  entry: {
    direction: "long" | "short" | "both";
    logic: "all" | "any";              // top-level combinator over `conditions`
    conditions: ConditionNode[];       // 1..12 LEAF conditions total (group leaves counted); depth ≤ 3
  };
  exits: {
    stopLoss: { kind: "atr"; atrMultiplier: number } | { kind: "pips"; pips: number };
    takeProfit: { kind: "rr"; ratio: number } | { kind: "atr"; atrMultiplier: number } | { kind: "none" };
    trailing?: { kind: "none" } | { kind: "atr"; atrMultiplier: number; activationR?: number };
    timeStop?: { kind: "none" } | { kind: "bars"; bars: number };
    oppositeSignalExit: boolean;
  };
  filters: {
    session?: { kind: "none" } | { kind: "window"; startHourUtc: number; endHourUtc: number }; // end exclusive, overnight allowed
    volatility?: { kind: "none" } | { kind: "atr-range"; minAtr?: number; maxAtr?: number };   // ATR(14) in price units
    spreadMaxBps?: number | null;
  };
  risk: {
    riskPerTradePct: number;           // 0.05 .. 5.0
    maxNotionalMult: number;           // notional ≤ equity × mult (≤ 5)
    leverageMax: number;               // informational cap in MVP (≤ 30); margin calls not simulated
    minStopPriceDistance?: number | null;
  };
  execution: { fillBasis: "next_open" };  // constant in v1 — documents the timing contract
  reservedForFuture?: {                   // MUST be absent or empty in v1; any content → reject NOT_SUPPORTED_IN_MVP
    partials?: unknown; pyramiding?: unknown; limitOrders?: unknown; stopEntryOrders?: unknown;
  };
};

type IndicatorDef =
  | { id: string; kind: "EMA"; period: number }            // 2..500
  | { id: string; kind: "SMA"; period: number }
  | { id: string; kind: "RSI"; period: number }            // 2..100, Wilder
  | { id: string; kind: "ATR"; period: number }            // Wilder, default 14
  | { id: string; kind: "MACD"; fast: number; slow: number; signal: number }
  | { id: string; kind: "BB"; period: number; stdDev: number }
  | { id: string; kind: "ADX"; period: number }
  | { id: string; kind: "Donchian"; period: number }
  | { id: string; kind: "VWAP"; kind2?: never }            // intraday reset; allowed but flagged low-confidence on FX/CFD in docs
  ;

type PriceField = "open"|"high"|"low"|"close";
type Operand =
  | { kind: "indicator"; ref: string; output?: string; offsetBars?: number }  // offsetBars ≥ 0 only (0 = just-closed value); negative = reject (lookahead)
  | { kind: "price"; field: PriceField; offsetBars?: number }
  | { kind: "const"; value: number };
// output selects a channel of multi-output indicators (MACD: macd|signal|histogram;
// BB: upper|middle|lower; Donchian: upper|lower|middle) and is REQUIRED for them.
// Single-output kinds take no selector (or "value"). A missing/invalid selector
// is STRATEGY_INVALID — the engine never guesses a channel.
// ATR linkage: exits/trailing with kind "atr" use the FIRST declared ATR indicator.
// Atr-based exits with no declared ATR indicator are STRATEGY_INVALID.

type Condition = {
  id: string;
  left: Operand;
  op: ">"|">="|"<"|"<="|"=="|"!="|"crossesAbove"|"crossesBelow";
  right: Operand;
};
type ConditionNode =
  | Condition                                    // leaf
  | { id: string; group: "all" | "any"; children: ConditionNode[] };  // branch (nesting depth ≤ 3)

// A v1 spec with a flat `conditions` list is the implicit top-level group: {group: logic, children: conditions}.
// There is deliberately no NOT operator in v1 — every expressible predicate has a positive form
// (</≤, >/≥, ==/!=, crossesAbove/crossesBelow); NOT over groups is deferred to avoid De Morgan
// validation complexity. Requesting it → NOT_SUPPORTED_IN_MVP with pointer.
// crossesAbove (a,b) at bar t ≡ a[t-1] ≤ b[t-1] AND a[t] > b[t] using closed-bar values only.
```

## Validation rules (implement exactly; error codes in `docs/api.md`)

1. `specVersion` must be `"1.0"`; unknown `kind` values reject.
2. Every `indicator.ref` in conditions/exits must resolve to a declared `indicators[].id`; ids unique.
3. `offsetBars` must be ≥ 0 integer; any negative → `LOOKAHEAD_OFFSET_REJECTED`.
4. Indicator-specific: `EMA.fast < EMA.slow` analogues not needed (refs are independent); MACD requires `fast < slow`; `BB.stdDev` 0.5..4; RSI/ATR/ADX periods in range; Donchian 2..500; VWAP subject to rule 4c.
4b. Group rules: leaf count across the whole tree 1..12; depth ≤ 3; ids unique across leaves and branches; empty branch → reject. `==`/`!=` on floats use epsilon `1e-9` (|a−b| ≤ eps counts as equal) — exact float equality never decides a trade.
4c. **VWAP guard:** VWAP requires nonzero volume (`Σv > 0` over the session). FX/metals datasets store volume 0 by default → declaring VWAP in a spec for those datasets (checked at run start against the resolved dataset) fails with `DATASET_INVALID` ("VWAP needs volume data; FX/metals samples are volume-less"). Prevents silent NaN/zero-division trades.
4d. **Session-filter granularity guard:** `filters.session.window` is rejected for `H4` and `D1` timeframes. Rationale: D1 bars open at 00:00 UTC only (a 07–20 window would silently produce zero trades forever); H4 opens at 0/4/8/12/16/20 (window matches arbitrary opens, semantically meaningless). Session windows are meaningful only on M5/M15. Requesting otherwise → `NOT_SUPPORTED_IN_MVP` with this explanation.
5. `risk.riskPerTradePct` 0.05..5; `rr` 0.25..10; ATR multipliers 0.25..10 (`activationR` 0.5..10, default 1.0); `bars` 1..500; session hours 0..24 integers; spread ≥ 0.
6. `reservedForFuture` non-empty → `NOT_SUPPORTED_IN_MVP` (do not silently ignore).
7. Cross-timeframe refs, tick refs, news-sentiment operands → `NOT_SUPPORTED_IN_MVP`.
8. Canonicalization before hashing: sort keys, round numerics to 6 dp, strip `reservedForFuture` absence vs `{}` equivalence (normalize to absent).

## Versioning

- Canonical JSON → `sha256` → `specHash` (first 16 hex chars shown in UI, full stored).
- New version on **any** spec byte change, even display-name-only? No — display name lives on `Strategy`, not spec; spec changes alone bump versions.
- `parentVersionId` chain + `provenance {actor, patchSummary}` preserved for audit and AI trace.

## Worked example (trend-pullback instance)

```json
{
  "specVersion": "1.0",
  "universe": { "symbol": "EURUSD", "timeframe": "M15" },
  "indicators": [
    { "id": "ema50", "kind": "EMA", "period": 50 },
    { "id": "ema200", "kind": "EMA", "period": 200 },
    { "id": "ema20", "kind": "EMA", "period": 20 },
    { "id": "atr14", "kind": "ATR", "period": 14 }
  ],
  "entry": {
    "direction": "long",
    "logic": "all",
    "conditions": [
      { "id": "c1", "left": { "kind": "indicator", "ref": "ema50" }, "op": ">", "right": { "kind": "indicator", "ref": "ema200" } },
      { "id": "c2", "left": { "kind": "price", "field": "close" }, "op": "<", "right": { "kind": "indicator", "ref": "ema20" } },
      { "id": "c3", "left": { "kind": "price", "field": "close" }, "op": ">", "right": { "kind": "price", "field": "close", "offsetBars": 1 } }
    ]
  },
  "exits": {
    "stopLoss": { "kind": "atr", "atrMultiplier": 1.5 },
    "takeProfit": { "kind": "rr", "ratio": 2 },
    "trailing": { "kind": "none" },
    "timeStop": { "kind": "none" },
    "oppositeSignalExit": true
  },
  "filters": {
    "session": { "kind": "window", "startHourUtc": 7, "endHourUtc": 20 },
    "volatility": { "kind": "none" },
    "spreadMaxBps": 25
  },
  "risk": { "riskPerTradePct": 0.5, "maxNotionalMult": 3, "leverageMax": 10 },
  "execution": { "fillBasis": "next_open" }
}
```

Reading: long only; uptrend (EMA50 > EMA200 on the just-closed bar); pullback (close below EMA20) with a bullish bar; session 07:00–20:00 UTC; 0.5% risk; 1.5-ATR stop, 2R target.

## Indicator semantics (normative for engine tests)

- EMA/SMA/MACD-signal: standard recursive/mean definitions, seeded from first available bar; values for the first `period-1` bars are marked `warmingUp: true` and **signals are suppressed** while any referenced indicator is warming up (prevents garbage early trades; disclosed as warning count).
- RSI: Wilder smoothing; ATR: Wilder true-range mean; ADX: Wilder DX smoothing; BB: SMA ± k·population-σ; Donchian: highest-high/lowest-low over N closed bars; VWAP: cumulative session reset at 00:00 UTC.
- All indicators computed **incrementally left-to-right**; a test helper `compute_indicators(bars)[t]` must equal engine-internal values at `t` (golden vectors in `backend/tests/fixtures/indicators/*.json`).

## Expressiveness limits (explicit, not silent)

Cannot express in v1: multi-timeframe confirmation, NOT-over-groups, candle-pattern libraries beyond comparisons/crosses, partial exits, scale-ins, limit/stop entries, news/earnings filters, portfolio-level hedging. Requests for these validate-reject with `NOT_SUPPORTED_IN_MVP` plus a pointer to the relevant template/ADR — never a hallucinated emulation. Nested AND/OR groups (depth ≤ 3) ARE supported — "trend AND (RSI-extreme OR pullback)" needs no future migration.
