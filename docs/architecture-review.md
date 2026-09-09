# Architecture review — adversarial pass (v2)

Date: 2026-09-09. Method: treat v1 architecture as hypothesis; attack each decision; fix the docs, not just append commentary. All fixes below are already reflected in the specs (this file is the audit trail, not a sidecar).

---

## Second-pass addendum (same date, fresh-eyes mandate)

A second full re-trace hunted specifically for what the first pass missed. Five new findings, all fixed in-place:

**N1 (critical) — CPU-bound engine on the event loop.** The async job model as first written let the pure-Python engine run in-process; a 200k-bar run holds the GIL for seconds, freezing SSE, every endpoint, and the other queued job. Fixed: `docs/backtest-engine.md §10` — sync path in FastAPI threadpool (sync `def`), async path in `ProcessPoolExecutor(2)` with plain-data handoff; import-safety + cross-host determinism + event-loop-liveness tests added; ADR 0007 revised.
**N2 (high) — idempotency race undefined.** Two concurrent identical submissions both miss the dedupe check; loser hits `UNIQUE(result_hash)` → 500. Fixed: catch-and-return-existing with `deduped: true` (`docs/api.md`), race test added.
**N3 (high) — cancel flag couldn't cross the process boundary.** In-memory flags die with process-pool dispatch. Fixed: DB-polled flag every 1k bars (engine §10, api.md).
**N4 (medium) — VWAP ÷ zero volume.** FX/metals datasets carry volume 0 by default; VWAP silently NaNs or divides by zero. Fixed: validation rule 4c rejects VWAP on volume-less datasets with an actionable message.
**N5 (medium) — session filter on H4/D1 is semantically broken.** D1 opens at 00:00 UTC only (07–20 window → zero trades forever, silently); H4 opens hourly-grid-incompatible. Fixed: rule 4d rejects session windows on H4/D1 with the explanation.
Minor: drawdown-curve provenance labeled (chart derives from downsampled equity; headline maxDD is full-resolution and authoritative); template registry seeded by migration with code-table mismatch failing startup; `ai_cache` key includes provider+model.

Second-pass verdict: engine semantics, strategy representation, data, reproducibility, and AI boundary survived unchanged in decision; the job-execution host was materially wrong and is now fixed. The pattern (first pass fixes domain correctness, second pass fixes runtime-host correctness) is exactly why this review was repeated.

---

## 1. Scenario walkthroughs (end-to-end traces)

**A — Simple EMA crossover.** Web form → `POST /strategies` (template `trend-pullback`) → v1 stored → launcher picks dataset (manifest shown) → `POST /backtests` → sync run (<200k bars) → run row + trades + metrics in one transaction → run view renders with `runId/resultHash` footer. Trace clean. Crack found: none blocking; confirmed `describe()` must come from API (fixed in `frontend.md`), else web duplicates template logic.

**B — AI adds ATR volatility filter.** Intent → `POST /ai/propose` (Gemini or ruled) → `StrategyPatch addFilter` → Pydantic validation → preview of ops (no auto-apply) → confirm → v2 with `parentVersionId` + `aiTraceId` → rerun. Crack found and fixed: contradictory multi-op patches (add+remove same id) had no defined semantics → now atomic apply-or-reject in `alphalab_core.apply_patch`, max 10 ops (`domain-model.md`, `ai-assistant.md`).

**C — Same-bar SL+TP.** Covered by pessimistic stop-first + `ambiguous` flag + exit-side spread precision (long exits at bid). Crack found and fixed: exit-side spread was described vaguely ("minus costs") — now exact per-direction formulas in `backtest-engine.md §3`, with a spread-side fixture required.

**D — Strategy changed after backtest; old result reopened.** Old run pins `strategyVersionId` + `specHash`; Strategy Coleman points at v3; `GET /backtests/:oldRun` returns immutable v1-based payload byte-identical (hash-verifiable). No crack — immutability triggers + content hashes hold. Noted trap: UI must always show the version number beside the strategy name (frontend contract).

**E — Bad data (gaps + duplicates).** Import: sort → keep-FIRST dedupe (now deterministic and documented; previously unspecified) → validate → gap-scan → manifest → hash. Engine pauses indicators across gaps, records `gapsEncountered`. Crack found and fixed: dedupe "keep which?" was undefined → keep-first + count (`market-data.md`); H4/D1 grid alignment was undefined → pinned to 00/04/…/20 UTC and 00:00 UTC.

**F — Long backtest crashes halfway.** Async job, crash mid-run. Crack found and fixed: partial-write semantics were unstated → now single-transaction run persistence (zero partial rows), startup recovery marks stuck `running` as `failed/restarted`, cancel is cooperative per 1k bars, browser-close is server-neutral (`api.md`).

**G — Concurrent sweeps.** 32-combo sweep → 32 jobs, concurrency 2, queue 20; 33rd combo rejected; duplicate submission dedupes by content key (`deduped: true`). No crack after fix; pressure point noted (queue is in-memory — restart drops queued items by design, documented).

**H — AI returns garbage.** Malformed JSON → `AI_VALIDATION_FAILED`, nothing applied; invented metrics → grounding check fails; stale `baseSpecHash` → rejected. No crack; added replay-fixture + footer-field contract tests (`testing.md`).

**I — Lookahead attempt.** Negative `offsetBars` → reject; future-bar mutation property test; crosses require t and t−1 non-warmup; warmup suppression. Crack found and fixed (the big one): **cold-start truncation** — slicing bars at `startTime` without pre-history silently mis-seeds EMA/ATR/RSI/ADX. Now the lookback rule: API supplies `warmupBars = max(3×maxPeriod, 50)` pre-bars, computation covers lookback, signals only in-range, deficit flagged `coldStart` (`backtest-engine.md §1.7`, cold-start equivalence test required).

**J — Future expansion (new asset class, TF, richer representation).** New symbol/TF = new dataset kind + instrument-meta version (no engine change). Richer representation = nested groups already shipped (no migration), order `kind`/position `legs[]` reserved under engine-version bump. Dead-end check passed after the groups fix (see §3).

## 2. Decisions that survived (attacked, kept)

- Declarative JSON strategies + no code execution (0002/0003): executable-code and DSL alternatives re-evaluated; sandbox burden + AI prompt-injection-to-RCE keeps the ban correct.
- Closed-bar/next-open/pessimistic-stops (0004): signal-close fills and tick-interpolation re-examined; both leak or invent precision. Kept, with precision hardening (§3 exits).
- One-position v1 scope: multi-position-on-day-one re-argued; half-correct ledger would poison comparisons. Kept as sequencing with documented `engine/2.0` seams.
- SQLite + immutable rows + content hashing (0006): Postgres/files-only re-examined; single-file audit trail still optimal for localhost; money-TEXT fix strengthens it.
- In-process asyncio queue, no Redis (0007): crash semantics now explicit rather than assumed; decision holds.
- Polyglot FastAPI+Vite + shared-schema contract (0009): single-language rollback considered; quant/AI ecosystem + user direction keep the polyglot, with drift-as-red-build as the load-bearing control.
- Free-tier Gemini BYOK + ruled fallback (0008/0010): rule-only rollback considered and rejected again — product needs live NL; constraints hold at $0 with fallback grace.

## 3. Decisions that changed (what was wrong)

1. **Flat AND/OR conditions → nested groups (depth ≤ 3, ≤12 leaves).** Wrong: single-level combinator couldn't express "trend AND (RSI-extreme OR pullback)" — the core template-composition need — guaranteeing a future migration cliff. Fixed in `strategy-spec.md`; `addGroup` patch op added; NOT-over-groups explicitly deferred with reason.
2. **Truncation seeding → warmup lookback rule.** Wrong: indicators seeded at `startTime` with no history = silently wrong early signals (a lookahead-adjacent correctness bug, the most dangerous class). Fixed with lookback window + `coldStart` warning + equivalence test.
3. **Vague exit costs → per-direction exit-side formulas.** Wrong: "minus costs" hid bid/ask asymmetry on exits. Fixed.
4. **Trailing vagueness → normative ratchet formula** with `activationR` semantics and default. Fixed.
5. **Reversal/pending-while-open undefined → two-leg reversal + pyramid-skip orders.** Wrong: `direction: both` with one position had no specified behavior. Fixed with stored order rows for every pending decision.
6. **Estimate-vs-fill sizing gap undisclosed → intended vs realized risk stored + `gapRiskExceeded` warning.** The quantity decision stays at signal time (correct), but the divergence is now measured, not hidden.
7. **Missing instrument-metadata domain → versioned `instrument_meta` in hash scope.** Wrong: lot steps affected sizing but weren't versioned/hashed — identical configs could diverge silently. Fixed across domain/persistence/hash-scope docs.
8. **Config identity clutter (`riskOverride`, engine `seed`) → removed.** Both forked or confused identity; risk lives in spec, determinism is seed-free.
9. **Sharpe guards insufficient → N≥30 AND bars≥100 AND sd>0**, plus fixed annualization table (M15 row was malformed) and `TOO_MANY_TRADES` cap. Fixed.
10. **Job crash/partial-write semantics unstated → atomic run transaction + recovery + idempotency + cooperative cancel.** Fixed in `api.md` + tests.
11. **Money in REAL columns → TEXT/Decimal** for qty/prices/fees/pnl; bars stay REAL (market data, not accounting). Fixed in `persistence.md`.
12. **Dedupe/grid/synthetic-PRNG underspecified → keep-first, H4/D1 grids, Python `random.Random`.** Fixed.
13. **AI patch application semantics → atomic `apply_patch` in core, max ops, contradiction rejection, PII note.** Fixed.
14. **Stale references** (ADR 0001 duplication, `packages/*` paths, Zod-only wordings, `make` vs `npm`, "no secrets" line, `describe()` ownership). Fixed.

## 4. Remaining uncertainties (genuinely undecided)

- Sweep-cap 32 vs higher: needs measured run-time data (see risks doc Q3).
- Demo-data licensing path (Q1) and leverage-copy sensitivity (Q2): product calls, defaults set.
- Whether Flash suffices for summaries long-term or Pro toggle earns its keep: instrument with token/quality logs, decide empirically.
- Future worker extraction (arq) trigger threshold: unknown until real workloads measured; seam preserved, no premature build.

## 5. Previously missed risks (found in this pass)

- Cold-start truncation mis-seeding (critical; fixed).
- Unversioned instrument metadata forking sizing identity (high; fixed).
- Reversal/pyramid undefined behavior under `direction: both` (high; fixed).
- Partial-run persistence on crash (medium; fixed).
- Float-equality conditions deciding trades (medium; fixed via epsilon).
- `==`/`!=` plus crosses warmup edge at first tradeable bar (medium; fixed).
- Sharpe explosion on flat equity (sd≈0) and malformed annualization table (medium; fixed).
- AI multi-op contradiction/partial application (medium; fixed via atomicity).

## 6. Architectural debt intentionally accepted

- No margin-call simulator (cap-only leverage, flagged per run).
- No multi-timeframe/resampling; no walk-forward optimizer (fields reserved).
- In-memory queue (restart drops queued, never partial results).
- No user-authored templates/marketplace; no custom indicators (registration API deferred to `engine/2.0` ADR).
- Lazy AI-cache expiry (stale-read miss, no janitor process).

## 7. Critical invariants (must never be violated)

1. `alphalab_core` pure: stdlib + numpy only; event loop explicit-index; no vectorized signal shifts.
2. Closed-bar signals, next-open earliest fill, pessimistic stop-first, exact-touch = hit.
3. Completed strategy_versions/datasets/runs immutable; edits create versions.
4. Same (specHash, datasetHash, configHash, engineVersion, instrumentMetaVersion) → identical resultHash.
5. Money in `Decimal`/TEXT; frontend never authoritative; AI never in money path.
6. AI output validated + grounded + user-confirmed before versioning; raw model text never applied.
7. Schema-first changes: shared schema → codegen → equivalence green; never one-language-only fields.
8. No key in logs/DB; aggregates/specs only to vendor.

## 8. Implementation traps (likely to get wrong)

- Seeding indicators from `startTime` instead of the lookback window.
- Vectorized pandas shifts for signals (`shift(-1)` = instant lookahead P0).
- Applying spread to entries but forgetting exit-side bid/ask asymmetry.
- Resizing at fill instead of signal (gap-risk distortion) — store both risks, don't re-size.
- Float `==` without epsilon; crosses without t−1 warmup check.
- Writing run rows outside a single transaction; forgetting startup recovery.
- Running the engine inline on the event loop (async def route + CPU-bound call = frozen API); using in-memory cancel flags with a process pool.
- Letting the dedupe loser 500 on `UNIQUE(result_hash)` instead of returning the winner.
- Adding a strategy field in Pydantic without the shared schema (equivalence test will catch — respect it).
- Caching AI summaries by runIds without metricsHash, or by content without provider+model (stale text after rerun/model switch).
- Declaring VWAP without checking dataset volume (NaN division on FX).

## 9. Future pressure points

- `engine/2.0` (multi-position matching rules FIFO/LIFO, partial-fill ledger, limit/stop entries) — biggest design load ahead; seams ready.
- Multi-timeframe resampling (lookahead-safe join semantics will need their own ADR).
- Postgres migration if multi-user/cloud arrives (repo isolation + user_id make it mechanical).
- Worker extraction if sweeps outgrow in-process (core importability preserved).
- Custom-indicator registry (permission model + determinism sandbox — ADR-gated).

## 10. Confidence assessment

- Backtest engine semantics: **high** (post-fix; every rule has a named fixture + property).
- Lookahead/data-leakage posture: **high** (contract + lookback + mutation tests + purity gate).
- Strategy representation: **high** (groups remove the migration cliff; ceiling explicit).
- Templates: **high** (pure constructors + API-served describe).
- Market data: **moderate-high** (grids/dedupe fixed; provider adapters unproven by design).
- Reproducibility: **high** (hash scope now complete incl. instrument meta + metrics version).
- AI boundary: **moderate-high** (validation/grounding/fallback solid; live-model behavior needs production observation).
- Jobs/concurrency: **moderate-high** (semantics explicit; restart-drops-queue accepted).
- Persistence: **high** (triggers + Decimal-TEXT + atomic runs).
- Polyglot contract: **moderate** (strongest process control in the architecture, but inherently two-toolchain — confidence comes from the equivalence gate holding in CI, which must be monitored, not assumed).

**Implementation-ready? Yes** — with the conditions above enforced as CI gates (purity, equivalence, exact-cent fixtures, hypothesis properties, replay AI tests, trigger tests). The architecture now states every behavior the implementation is likely to get wrong, and each has a test that fails if it does.
