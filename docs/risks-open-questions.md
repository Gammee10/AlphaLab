# Risks, brief challenges, open product questions

## Challenges to the brief (resolved by architecture — binding unless user overrides)

1. **Must change — §6 implied full order-type/position matrix in MVP.** Realistic multi-position + partials + limit/stop entries on OHLCV is a research-grade simulator project on its own; half-built it produces misleading fills (worse than no feature). → Cut to one-position, market + attached SL/TP (schema reserves the rest, engine rejects with `NOT_SUPPORTED_IN_MVP`). Revisit as `engine/2.0` ADR. The cut is sequenced, not structural — `docs/backtest-engine.md §9` shows the per-seam extension (order kinds, multi-leg positions, partial fills) reusing the same ledger and hash contract.
2. **Must change — "tick-accurate realism" expectation on bar data.** Without ticks, intrabar stop/target order is unknowable. → Pessimistic ordering (stop-first) + `ambiguousBars` count + per-trade `ambiguous` flag. Curves look slightly worse and are honest.
3. **Recommended — equities as MVP instruments.** Splits/dividends/screener scope add error surface with no research-loop benefit. → FX/metals/crypto spot only in MVP.
4. **Recommended — live data providers in MVP.** Licensing, key management, and non-reproducible pulls undermine the reproducibility promise. → CSV + samples + synthetic in MVP; provider port ready.
5. **Recommended — walk-forward optimizer in MVP.** Needs nested versioning semantics the MVP shouldn't lock in prematurely. → Data-split fields exist; optimizer deferred.

## Top technical risks (updated for polyglot + free-tier AI)

| # | Risk | Likelihood / Impact | Mitigation (built into architecture) |
|---|---|---|---|
| 1 | Lookahead creep (incl. numpy vector-shift leaks) | M / Critical | Explicit-index event loop (no vectorized signals), causal-only numpy kernels, `offsetBars ≥ 0` validation, hypothesis future-mutation property tests, pure `alphalab_core` |
| 2 | Pydantic/Zod schema drift | M / High | Single `shared/schemas/strategy.spec.json` + codegen + CI equivalence tests; drift = red build |
| 3 | Float drift in accounting | M / High | `Decimal` for cash/fees/notional, exact-cent fixtures, canonical rounding |
| 4 | Ambiguous-bar frequency underestimated on low TFs | H / Medium | Always-count + disclose; sensitivity guidance (run slippage 0 vs 5) in UI copy |
| 5 | Gemini quota/latency variability, key friction | H / Medium | BYOK + budgets + content-hash caching + quota→ruled fallback with banner; replay-based CI (no live key); footer on every AI surface |
| 6 | SQLite scale wall (>2M bars, concurrent sweeps) | L(MVP) / Medium | Caps + asyncio queue; shard path documented; `alphalab_core` stays importable by future workers |
| 7 | Overfit-looking results presented as edge | H / High | Warnings panel, in/out-of-sample fields, experiment diff discipline, "simulation ≠ future performance" banner spec'd in frontend |

## Product questions — full explanations (your three)

### Q1. Demo data: synthetic by default, or bundle a small real FX sample?

**Why it matters more than it looks.** First-launch experience decides whether you can evaluate the product at all: with no data, "one-click backtest" is a dead button and every template preview is hypothetical. But real market data carries redistribution licensing (vendor T&Cs, exchange rights) and provenance burden — shipping someone else's bars inside the repo can create liability and makes reproducibility claims ("dataset Z") depend on a third party's permission.
**Options.** (a) Synthetic-only bundle (seeded generator, ~50k bars across the 4 symbols): zero license risk, works offline, but curves look "too clean" and spread/gap behavior is idealized — you may under-trust or over-trust what you see. (b) Small attributed real sample (e.g. 2y EURUSD H1 ≈ 12k bars from a permissively licensed source like Dukascopy free data with attribution): realistic gaps/spreads, far more convincing evaluation, but requires verifying the license allows redistribution and pinning provenance metadata. (c) Downloader script (no bundled real data; one command fetches free data at first run): sidesteps redistribution but needs network + key handling on day one.
**Recommendation.** (a) for the repo default + (c) as a documented one-command optional fetch. Nothing in the architecture changes either way (datasets hash identically regardless of source). If you secure a redistribution-safe source, (b) slots in as `data/samples/eurusd_h1.csv` with no code change.
**If undecided:** implementation proceeds with (a); the import path already proves real-data handling via your own CSVs.

### Q2. Leverage: show capped leverage/notional, or hide it until margin-call simulation exists?

**Why it's sensitive.** Leverage displayed next to P&L implies broker-realism. MVP models leverage as a *cap* (`notional ≤ equity × maxNotionalMult`, `marginCallSimulated: false` stored per run) — it does not simulate margin calls, liquidation cascades, or funding. A user seeing "10×" beside a smooth equity curve can reasonably but wrongly conclude the strategy survives broker margin logic.
**Options.** (a) Show caps with explicit labeling (current design): preserves the risk-sizing input researchers expect (position sizing needs the cap to be meaningful), with persistent "caps only — no margin-call simulation" disclosure on every run view. Slight misread risk, mitigated by copy. (b) Hide leverage entirely until a real margin simulator lands: zero misread risk, but position sizing loses its ceiling input, backtests silently assume infinite buying power except cash — arguably *less* realistic, and the field must be reintroduced later with migration-adjacent UX churn.
**Recommendation.** (a) — the disclosure is cheaper than the distortion of uncapped sizing, and the stored `marginCallSimulated: false` flag keeps future margin work honest (it flips to versioned simulation under a new engine version rather than rewriting history).
**If undecided:** (a) ships; hiding it later is a one-line UI change since the backend flag already exists.

### Q3. Sweep limit: is 32 runs per sweep acceptable for v1, or do you need larger grids now?

**Why 32.** A sweep is N full backtests queued as one experiment. Cost scales linearly (bars × runs ÷ concurrency 2, 120s timeout each). 32 × 200k-bar runs is already ~minutes of compute and a comparison table at the edge of human readability — beyond that, results need ranking/statistics UX the MVP doesn't have, and a single user action can wedge the queue for everyone (localhost: for you, blocking your own next experiment).
**Options.** (a) 32 hard cap (current): forces thoughtful grids (e.g. 4 stops × 4 markets × 2 periods), keeps the queue responsive, comparison view stays legible. (b) Higher cap (128+) now: requires queue priority, progress aggregation, and result-ranking UI to stay usable — real work, not just a constant change. (c) Paginated/async-only large sweeps: same as (b) with more machinery.
**Recommendation.** (a) for MVP with the cap as config (`sweep.max_combos`), so raising it later is an ops decision informed by measured run times, not an architecture change.
**If undecided:** (a) ships; your first slow sweep will produce the timing data needed to justify (b).
