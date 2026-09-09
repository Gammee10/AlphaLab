# AlphaLab Codebase Improvement Audit

> Scope: full repo (`backend/`, `web/`, `shared/schemas/`, `docs/`, `data/samples/`, `Makefile`, `.github/`).
> Method: full file reads of engine, indicators, metrics, market-data, contracts, API, store, AI, frontend, tests, docs; spot-verification of the highest-severity claims against the implementation.
> Rule followed: every finding below is grounded in observed code/docs. Where a claim needs a runtime check, it is labeled **Assumption requiring verification**.
> Application code was not modified for this audit.

## Executive Summary

**Overall assessment.** AlphaLab has a genuinely good architecture for a research system: an explicit purity boundary (`alphalab_core` = stdlib+numpy only), closed-bar/next-open execution semantics, pessimistic stop-first ambiguity rule, Decimal money math, immutable versioned rows, and honest MVP scope cuts. The docs (`ARCHITECTURE.md`, `docs/backtest-engine.md`, `docs/testing.md`, `docs/security.md`, `AGENTS.md`) set a high bar. The implementation meets most of that bar but falls short exactly where it hurts a research platform: **a small number of execution/accounting edge cases that silently flatter results**, plus **job-lifecycle and input-validation gaps that can corrupt queues, leak internals, or 500 on bad input**, plus **missing enforcement for the determinism/no-lookahead guarantees the docs promise** (zero property tests, missing run fixtures, unpinned deps, unenforced CI gates).

**Totals:** 48 findings — Critical: 7, High: 16, Medium: 17, Low: 6, Optional: 2.

| Severity | Count | Meaning in this report |
|---|---|---|
| Critical | 7 | Could produce materially incorrect backtests, break prod, corrupt data/queue, or leak secrets |
| High | 16 | Significant correctness, security, reliability, or architectural problem |
| Medium | 17 | Meaningful, should be fixed, not immediately critical |
| Low | 6 | Minor / tech debt |
| Optional | 2 | Nice-to-have refinements |

**Most important areas requiring attention:**

1. **Backtest correctness (execution edge cases):** gap-through-stop fill price (C1), end-of-data exit costs (H1), both-fire tie-break asymmetry (H2), sizing/cap on estimate vs fill (M2). These directly move P&L.
2. **Job lifecycle / reliability:** sync-path bypass of concurrency limits (C2), orphaned `queued` rows (C3), sweep without rollback (C4), per-request engine creation + SQLite contention (C6).
3. **Input validation / error handling:** unvalidated money/time inputs → 500s (C5), `httpx` missing from prod requirements (C7), internal error text persisted/streamed (H7).
4. **Security honesty:** key-in-URL + no redaction filter (H8), dead token budget (H9), `user_id` filtering promised but absent (H10), unbounded AI/cache/CSV surfaces (M-section).
5. **Guarantee enforcement:** zero hypothesis property tests (H13), missing hand-computed run fixtures (H14), unpinned backend deps (H15), CI missing 3 of 4 documented gates (H16), codegen hardcodes 3 enum lists (M12).
6. **Frontend authority violations:** drawdown recomputed in float in `web/` (H3), error details discarded (H4), missing loading/error states (H5).

A backtest that is wrong in the favorable direction is worse than a crash. Fix the Critical + High backtest items first, even before security hardening, because every stored run created before the fix is suspect.

---

## 1. Critical findings

### C1 — Gap-through-stop pays the stop price instead of the adverse open [IMPLEMENTED]

> **Implementation note (2026-09-09):** Fixed in `engine/1.1`. Stop exits are now capped at the open-adverse price (`min(s_px, open_adv)` long / `max(...)` short) on any bar, with a new `warnings.gapThroughStop` counter + assumptions disclosure. Gap-through-target still fills at `T` (pessimistic, documented). Changed: `backend/alphalab_core/engine.py`, `config.py` (`ENGINE_VERSION=engine/1.1`), `alphalab_api/service.py` (config identity now uses `ENGINE_VERSION` instead of a hardcoded string), `docs/backtest-engine.md` (version + changelog + §3 rule), `backend/tests/test_engine.py` (updated gap test + 3 new: short gap, exact-to-stop, gap+both-touched), `test_api.py` (asserts `ENGINE_VERSION`). Validated: `test_engine.py` 21 passed; full backend suite 116 passed (excl. perf). Behavioral change: old `engine/1.0` runs with gap-through-stop exits are not comparable to `engine/1.1` runs.

- **Category:** Backtesting Correctness / Execution Simulation
- **Severity:** Critical
- **Location:** `backend/alphalab_core/engine.py:518-529` (`run_backtest`, intrabar phase); contradicts `docs/backtest-engine.md:48` (fill-at-open + stop same-bar at open-adverse side).
- **Evidence:** Long branch computes `s_px = s - spread_amt(s) - slip_amt(s)`, sets `hit_stop = l <= s`, then `close_position(i, s_px, ...)` regardless of where bar `i` opened. If bar `i` gaps down through the stop (`open[i] << s`), the fill is still `s_px`. The unit test `test_gap_through_stop` encodes this: stop `100`, exit recorded at `100` for a long bought below its stop (a profit on a stop-out).
- **Why it matters:** Backtest-invalidating. Every overnight/weekend gap through a stop is mispriced in the trader's favor. Stop-heavy strategies look better than reality; gap risk is understated.
- **Recommended fix:** On any bar where the position is open at the open (including bars where the stop was already touched by the gap), cap the exit adversely: long `exit = min(s_px, open_adverse_bid)`; short `exit = max(s_px, open_adverse_ask)`, where open-adverse includes spread/slippage at the open. The conservative equivalent satisfying the doc is: if `open` is beyond the stop, exit at the open-adverse price and mark `ambiguous=True`.
- **Implementation guidance:**
  1. Add helper `open_adverse_price(i, direction)` reusing `exit_price_at_open`.
  2. In both long/short stop branches: `px = min(s_px, open_adv)` (long) / `max(...)` (short).
  3. Add `warnings["gapThroughStop"]` counter; surface in assumptions.
  4. Files: `engine.py` only; no schema change.
  5. Edge cases: stop == open exactly (no gap, keep `s_px`); both stop+target touched + gap (stop-first still wins, at adverse open); trailing stops (same rule applies to trailed level).
- **Validation:** New known-answer tests: long gap-down through stop, short gap-up through stop, gap exactly to stop, gap + both-touched. Hand-compute exit, fees, net P&L to the cent. Add synthetic gap fixture. Re-run golden runs and record hash changes in an ADR/migration note (old hashes were wrong).

### C2 — Sync backtest path bypasses all concurrency/queue limits (DoS + threadpool exhaustion)

- **Category:** Reliability / API / Performance
- **Severity:** Critical
- **Location:** `backend/alphalab_api/routes_runs.py:55-66`; `backend/alphalab_api/jobs.py:178-208` (`execute_sync`); limits defined in `backend/alphalab_api/settings.py:15-17`.
- **Evidence:** `if bar_count < settings.sync_bar_threshold: execute_sync(...)` with no `queued_depth` check and no semaphore/timeout/cancel in `execute_sync`. The `job_concurrency=2 / job_queue_limit=20` gates only the async branch. Sweeps compound it: `routes_runs.py:331-334` loops `execute_sync` up to 32× inside one request handler.
- **Why it matters:** Normal reliability issue with research consequences: a burst of `<200k`-bar requests (or one 32-combo sweep) blocks FastAPI workers/CPU; results time out and users re-submit, compounding load. Not a backtest-math bug but can produce partial/failed research.
- **Recommended fix:** Gate sync path with the same semaphore + queue-depth check; add timeout to sync execution (run engine in worker thread with timeout, mark job failed on expiry); cap sweep sync work per request (e.g., force async when `combos * bars` exceeds threshold).
- **Implementation guidance:** Share one `asyncio.Semaphore(job_concurrency)` across both paths (fix global-singleton issue in H6 at the same time); wrap `run_backtest` call in `asyncio.wait_for`; on timeout set job error `TIMEOUT`. Files: `routes_runs.py`, `jobs.py`, `settings.py`.
- **Validation:** Concurrency test: fire N sync requests against `job_concurrency=1`, assert at most 1 runs and the rest 429/queued; sweep-of-32 test asserts bounded latency or async upgrade; load test with 200k-bar dataset.

### C3 — Sync failure orphans a `queued` job row that permanently inflates queue depth

- **Category:** Reliability / Database
- **Severity:** Critical
- **Location:** `backend/alphalab_api/jobs.py:183-188`; `backend/alphalab_store/repos.py:186-194` (`recover_interrupted`); `jobs.py:50-58` (`queued_depth`).
- **Evidence:** `execute_sync` creates + commits the job, then calls `run_backtest`; any raise leaves state `queued` with no `finish_job`. Recovery only fixes `running`. `queued_depth` counts `queued+running`, so orphans accumulate toward false `429`s.
- **Why it matters:** Reliability/data-integrity. A single bad input that throws inside the engine can wedge the queue until manual DB surgery.
- **Recommended fix:** Wrap `execute_sync` engine call in try/except → `finish_job(job_id, state="failed", error=...)`; extend startup recovery to requeue/fail stale `queued` rows older than N minutes; add DB check constraint or janitor job.
- **Implementation guidance:** Files `jobs.py`, `repos.py`, `app.py` lifespan. Add `started_at` on sync start so staleness is detectable.
- **Validation:** Test: sync run that raises → job is `failed`, `queued_depth` unchanged; restart-recovery test with stale `queued` row.

### C4 — Sweep commits versions then runs unguarded: partial failure = 500 + orphaned versions/runs, no experiment

- **Category:** Reliability / API
- **Severity:** Critical
- **Location:** `backend/alphalab_api/routes_runs.py:330-334` (`session.commit()` then per-combo `execute_sync` with no try/except); `_ephemeral_version` at `routes_runs.py:359-368`.
- **Evidence:** Versions committed before any run executes; a mid-loop `TooManyTrades`/`ValidationError`/`KeyError` propagates as 500 after earlier combos persisted, including a throwaway `sweep-base` strategy per call. No rollback, no per-run error aggregation.
- **Recommended fix:** Run all combos with per-combo try/except, collect `{combo, runId | error}`; create the experiment only from successful runs; return 207-style multi-status or a summary object `{runs, failures}`; never create throwaway strategies on the happy path (reuse one ephemeral version per sweep).
- **Implementation guidance:** Files `routes_runs.py`, `service.py`. Decide contract first (update `docs/api.md`), then implement; add test for mid-sweep failure.
- **Validation:** Sweep test with 3 combos where combo 2 is invalid → 200/207 with 2 runs + 1 typed failure, experiment contains only successes, no stray strategies.

### C5 — Unvalidated money/cost/time inputs reach `Decimal()`/`int()` and crash as 500; negatives accepted [IMPLEMENTED]

> **Implementation note (2026-09-09):** Fixed with a shared validator instead of the suggested Pydantic models (keeps the 400+code error contract; strict Pydantic fields would have produced 422s). New `_request_dict_from_config()` in `routes_runs.py` validates times (int/int-string, bool/float rejected, range-checked), `initialCapital` (finite, 0 < x ≤ 1e12), and present cost keys (finite, 0 ≤ x ≤ caps); all failures raise `ValidationError` → 400. Both `POST /backtests` and `POST /experiments/sweep` route through it — sweep validation runs before any version is committed, so bad configs no longer orphan versions, and missing sweep `startTime` is 400 instead of 404-`KeyError`. `deps.py` additionally maps `decimal.InvalidOperation` → 400 as a backstop; `ValueError` is deliberately NOT blanket-mapped (engine bugs raise it and must stay loud 500s) — a documented deviation from the audit's recommendation. Changed: `backend/alphalab_api/routes_runs.py`, `deps.py`. Added `test_backtest_rejects_bad_config` (13 bad-input cases incl. NaN/Infinity/garbage/negative/bool/float, plus sweep-missing-times). Validated: full backend suite 122 passed (excl. perf); mypy clean.

- **Category:** API / Validation / Trading Logic
- **Severity:** Critical
- **Location:** `backend/alphalab_api/service.py:60-66,109-110,147,208`; error mapping in `backend/alphalab_api/deps.py:28-42`; sweep bypass at `routes_runs.py:332`.
- **Evidence:** `Decimal(str(...))` on costs, `int(request["startTime"])`, `Decimal(cfg["initialCapital"])` with no range checks; only `AlphaLabError/KeyError/TooManyTrades/MarketDatasetInvalid` are mapped, so `ValueError/InvalidOperation` escape as 500. Negative/huge `spreadBps/slippageBps/commissionPerUnit/initialCapital` accepted. Sweep passes raw `baseConfig` without `_request_dict` validation, so a missing `startTime` raises `KeyError` → misreported as 404.
- **Why it matters:** Both reliability and research-validity: negative costs produce flattering P&L; 500s on typos destroy iteration UX; wrong-status errors break the typed client.
- **Recommended fix:** Validate all numeric inputs with Pydantic v2 models (ranges: costs ≥ 0 with upper sanity caps, capital > 0, times int > 0, `startTime < endTime`); route sweep through the same validator; map `ValidationError` → 400 `STRATEGY_INVALID`/`CONFIG_INVALID` with per-field issues.
- **Implementation guidance:** Introduce `RunRequest`/`SweepRequest` models in `alphalab_contracts/runs.py`; use them in both `routes_runs.py` paths; fix `deps.py` to map `ValueError`/`InvalidOperation` defensively. Add frontend pre-validation (M14) as defense in depth.
- **Validation:** Parametrized API tests: negative/NaN/huge/missing fields → 400 with typed code, never 500; sweep with missing `startTime` → 400 not 404; property test that random invalid configs never 500.

### C6 — New SQLAlchemy engine per call, never disposed; raw sqlite3 worker contends with WAL pool

- **Category:** Performance / Reliability / Database
- **Severity:** Critical
- **Location:** `backend/alphalab_store/database.py:36-37`; call sites `deps.py:23-25`, `jobs.py:51,106,182`; `backend/alphalab_api/worker.py:26,41`.
- **Evidence:** `session_factory()` → `make_engine()` on every call; callers create factories per request/poll/task. Engines/pools accumulate (fds, SQLite locks). Worker opens raw `sqlite3` connections (cancel poll without timeout; progress with `timeout=10.0`) contending with the WAL writer → `SQLITE_BUSY` at the documented concurrency of 2.
- **Why it matters:** Resource leak + lock contention; under real 2-job concurrency this produces flaky `SQLITE_BUSY` failures and fd growth — failed research, not wrong research.
- **Recommended fix:** Single application-scoped engine + `sessionmaker` (lifespan-managed, disposed on shutdown); worker uses the same engine or a bounded connection with `busy_timeout`; enable `PRAGMA journal_mode=WAL; synchronous=NORMAL; busy_timeout=5000` in one place.
- **Implementation guidance:** Files `database.py`, `app.py` (lifespan), `deps.py`, `jobs.py`, `worker.py`. Careful with tests using tmp DBs — provide factory override fixture.
- **Validation:** Soak test: 2 concurrent async jobs × several waves, assert zero `SQLITE_BUSY`; fd/engine-count assertion (exactly 1 engine per app); startup/shutdown disposal test.

### C7 — `httpx` imported but missing from production requirements (all `/api/ai/*` broken on prod install) [IMPLEMENTED]

> **Implementation note (2026-09-09):** Fixed both halves. `httpx>=0.27` added to `backend/requirements.txt`; top-level import removed from `routes_ai.py` in favor of a lazy import inside `_live_request_fn`, so AI routes import without httpx installed. If a Gemini path is ever reached without httpx, it now falls back to the rule-based provider with honest `fallbackReason: "transport"` (new `_httpx_available()` probe checked in propose/explain/summarize) instead of raising ImportError. Changed: `backend/requirements.txt`, `backend/alphalab_api/routes_ai.py`. Added `test_routes_import_without_httpx` (module reloads with httpx blocked) and `test_propose_transport_fallback` (key set + no transport → ruled + `transport` reason). Validated: ai route suites 11 passed; mypy clean on `routes_ai.py`.

- **Category:** DevOps / Dependencies / API
- **Severity:** Critical
- **Location:** `backend/alphalab_api/routes_ai.py:15` vs `backend/requirements.txt:1-6` (no `httpx`); present only in `requirements-dev.txt:6`.
- **Evidence:** Prod install path (`pip install -r backend/requirements.txt`) makes every `/api/ai/*` import fail. CI masks it by installing `-dev`. Verified by file comparison.
- **Why it matters:** Complete AI-surface outage in any clean deployment; core backtests unaffected (good boundary) but the headline AI loop is dead.
- **Recommended fix:** Move `httpx` (pinned) into `requirements.txt`; or make the import lazy inside the Gemini live path so rule-based fallback works without it. Do both: pin it *and* lazy-import.
- **Implementation guidance:** One-line requirements change + `try/except ImportError` around the live-request import with graceful fallback. Add a CI job that installs prod-only requirements and imports the app.
- **Validation:** Fresh venv, `pip install -r backend/requirements.txt`, `python -c "import alphalab_api.app"` green; AI routes import without dev deps.

---

## 2. High findings

### H1 — End-of-data force-close skips spread/slippage (last trade flattered) [IMPLEMENTED]

> **Implementation note (2026-09-09):** Fixed in `engine/1.2`. Force-close now uses a direction-aware `exit_price_at_close()` (close ± spread/2 ± slippage; commission was already charged in `close_position`). Changed: `backend/alphalab_core/engine.py`, `config.py` (`ENGINE_VERSION=engine/1.2`), `docs/backtest-engine.md` (version + changelog + end-of-data rule). Added `test_end_of_data_exit_pays_exit_costs` (exact-cent: fill 102.51, exit 102.485, fees 200, gross −2.5). Validated: engine+api+runs+jobs suites 37 passed.

- **Category:** Backtesting Correctness
- **Severity:** High
- **Location:** `backend/alphalab_core/engine.py:569-571` vs normal exits (`engine.py:231-235,519-532`).
- **Evidence:** `close_position(last, money(bars.close[last]), "end-of-data")` uses raw close; normal exits use `exit_price_at_open()`/`s_px`/`t_px` with spread+slip. Commission still taken in `close_position`; spread/slip not.
- **Why it matters:** Backtest-invalidating for any run ending with an open position (common in trend strategies and in `test_pyramid_skip`): last-trade `net_pnl` overstated by round-trip friction.
- **Fix:** Apply the same adverse-side exit cost at force-close: `close_position(last, exit_price_at_close(last, direction), ...)`. Add counter `endOfDataCloses`.
- **Validation:** Known-answer test: position open at last bar → exit == close ± spread ± slip ± commission to the cent; regression on existing fixtures.

### H2 — Both-fire tie-break is asymmetric when holding (`long wins` only when flat/short-held) [IMPLEMENTED]

> **Implementation note (2026-09-09):** Fixed in `engine/1.3`. Entry legs are now collected first and `["long", "short"]` collapses to `["long"]` before inventory handling, so long wins whether flat (opens long), long-held (pyramid skip, no reversal), or short-held (reverses to long). Changed: `backend/alphalab_core/engine.py` (entry block + docstring), `config.py` (`ENGINE_VERSION=engine/1.3`), `docs/backtest-engine.md` (version + changelog + direction semantics). Added `test_both_fire_long_wins_regardless_of_inventory` (self-mirroring `!=` condition fires both sides every bar; asserts 1 long trade, no `opposite` exits, 3 pyramid skips). Validated: full backend suite 118 passed (excl. perf).

- **Category:** Backtesting Correctness
- **Severity:** High
- **Location:** `backend/alphalab_core/engine.py:474-495`; header comment `engine.py:12` and `docs/backtest-engine.md:32-33` promise symmetric `long wins`.
- **Evidence:** Flat + both-fire: opens long then `break`, stays long. Holding long + both-fire: first leg logs `ignored_pyramid`, second leg closes long + opens short. Holding short + both-fire: closes short + opens long then `break`. Same-bar resolution depends on inventory.
- **Why it matters:** Backtest-invalidating for `direction=both` in chop: reversal timing and trade count depend on current position, contradicting the documented rule.
- **Fix:** Evaluate both sides first, then apply one deterministic rule: if both fire and flat → open long; if holding and both fire → treat as `ignored_pyramid` for the same-side leg and reverse only if the spec says opposite-exit wins (document whichever is chosen). Simplest correct: both-fire while holding = keep holding + count `ambiguousSignal`, unless `oppositeSignalExit` is set (then reverse once).
- **Validation:** 3-position matrix test (flat/long-held/short-held × both-fire) asserting identical resolution; update docstring + `docs/backtest-engine.md`.

### H3 — `web/` recomputes drawdown in float (frontend money authority violation)

- **Category:** Frontend / Trading Logic
- **Severity:** High
- **Location:** `web/src/charts.tsx:110-118`; `web/src/format.ts`; violates `AGENTS.md §2`, `ARCHITECTURE.md §4`. The supposed grep-gate references `formatters/`, a directory that does not exist.
- **Evidence:** `EquityChart` does `Number(e)` + running-peak subtraction, discarding server `Decimal` exactness. `fmtMoney` (`format.ts:4-9`) parses Decimal strings through `Number` (precision loss past 2^53, hardcoded `en-US` locale). `MonthlyHeatmap` rounds to whole dollars.
- **Why it matters:** Displayed drawdown/P&L can disagree with stored metrics — the exact misleading-presentation failure the architecture forbids. Normal-quality issue with research-misleading consequences.
- **Fix:** Render server-computed drawdown series/values only; delete client-side peak math; fix `fmtMoney` to format Decimal strings without float conversion (string-based grouping, 2dp); fix the grep-gate path to the real files.
- **Validation:** Frontend test asserting no `Math.max`/peak arithmetic in `charts.tsx`; visual diff of chart vs server metrics on fixture run; add the money-keyword grep gate to CI with correct paths.

### H4 — Typed server validation details discarded at the API boundary

- **Category:** Frontend / API
- **Severity:** High
- **Location:** `web/src/api.ts:69-85`; producers in `backend/alphalab_contracts/errors.py:29-38`; swallowed in `Launcher.tsx:46,70`, `AiPanel.tsx:31,40`, `Compare.tsx:23`, `Strategies.tsx:51`, `StrategyDetail.tsx:57`.
- **Evidence:** `req<T>` keeps only `message`/`code`; `details.issues[]` never reaches forms; every view renders `` `${e.code}: ${e.message}` ``.
- **Why it matters:** Users cannot see per-field errors the backend carefully builds; strategy iteration UX degrades to guessing. Reliability/UX, not math.
- **Fix:** Extend `ApiError` with `details?: {issues: {path, message}[]}`; map issues to fields in StrategyDetail/Launcher; add component test.
- **Validation:** Test with invalid spec asserting per-field messages render next to the right inputs.

### H5 — Dashboard / Strategies have no loading or error states; failed fetch looks like "no data"

- **Category:** Frontend / Reliability
- **Severity:** High
- **Location:** `web/src/views/Dashboard.tsx:6-9`, `web/src/views/Strategies.tsx:36-37`.
- **Evidence:** No `isLoading`/`isError` branches; failed fetch renders `"…"` / empty lists forever; only the sidebar health dot hints at outage.
- **Why it matters:** Silent dead UI; users mistake outage for empty research. Also `RunView` fires `datasetBars(id, 0, 0)` before real times resolve (`RunView.tsx:12-18`) and `Compare` fails atomically on one bad run (`Compare.tsx:29-33`).
- **Fix:** Add loading skeletons + error banners with retry on all views; gate bars query on resolved `startTime/endTime`; make Compare per-run fault-isolated.
- **Validation:** Component tests with mocked failing queries asserting error UI + retry works.

### H6 — Global semaphore/executor singletons ignore later settings and serialize DB I/O

- **Category:** Architecture / Reliability
- **Severity:** High
- **Location:** `backend/alphalab_api/jobs.py:32-47,107+`.
- **Evidence:** `_executor`/`_semaphore` module globals bound on first use to the first settings' `job_concurrency`; tests with tmp DBs share one limiter; semaphore held across prepare + engine + persist, serializing DB I/O unnecessarily.
- **Fix (with C6):** Move executor+semaphore into app lifespan state keyed off current settings; hold the semaphore only around the CPU-bound engine call, not DB prepare/persist.
- **Validation:** Test changing `job_concurrency` takes effect without restart; concurrency test showing DB I/O overlaps.

### H7 — Internal exception text persisted to `job.error` and streamed to clients

- **Category:** Security / API
- **Severity:** High
- **Location:** `backend/alphalab_api/jobs.py:137,173-174`; surfaced via `GET /jobs/:id` and SSE `routes_runs.py:158-176`.
- **Evidence:** `f"INTERNAL: {exc}"` / `f"{code}: {exc}"` store raw tracebacks/DB/Decimal text; contradicts `docs/api.md:60` ("500 internal, no stack to client") and the `security.md` redaction claim (no redact/logger code exists in `alphalab_api`).
- **Fix:** Persist internal detail to server logs only; store a stable code + request id in `job.error`; add the promised redaction filter (`key|token|secret|authorization`) to all logging.
- **Validation:** Failure test asserting response/row contains code + id but no traceback/SQL/paths; grep test that no `exc` interpolation reaches the DB model.

### H8 — Gemini key sent in URL query string; promised log redaction does not exist

- **Category:** Security
- **Severity:** High
- **Location:** `backend/alphalab_ai/gemini.py:48-49,66-67`; `backend/alphalab_api/routes_ai.py:36-44`; promises in `docs/security.md:6,14,17`.
- **Evidence:** `...:generateContent?key={key}` posts with no redaction; no `redact|logging|logger` filter in `alphalab_api`; error path reflects `body_text[:200]` into `ModelError` → API response.
- **Fix:** Send key via `x-goog-api-key` header (Gemini supports header auth), never in URL; add central redaction for logs/errors; truncate + sanitize provider error bodies.
- **Validation:** Test asserting no `key=` URL construction; log-capture test with fake key asserting redaction; error-path test with malicious provider body.

### H9 — `ai_daily_input_tokens` budget is dead config (spend unbounded)

- **Category:** Security / Reliability / Cost
- **Severity:** High
- **Location:** `backend/alphalab_api/settings.py:22`; zero reads/writes repo-wide; promised in `docs/ai-assistant.md`.
- **Evidence:** `200_000` defined but never enforced.
- **Fix:** Token ledger table (or `ai_traces` daily sum) checked before each Gemini call; 429 `AI_QUOTA` when exhausted; surface `quota.remainingToday` truthfully (also fixes doc drift in M5).
- **Validation:** Test with tiny budget asserting second call 429s and fallback engages.

### H10 — Ownership/`user_id` filtering promised but absent (IDOR by UUID when multi-user arrives)

- **Category:** Security / Architecture
- **Severity:** High (Medium risk today on localhost, High for the stated multi-user future)
- **Location:** `backend/alphalab_store/repos.py:81,276` (only two checks) vs `docs/security.md:16` ("every repo query filters `user_id`"); `routes_runs.py:228-234`, `get_strategy_version`, `get_run`, `get_dataset_bars` take bare IDs. `GET /api/versions/:versionId` from `docs/api.md:13` is not implemented.
- **Evidence:** Direct code comparison; UUID-guessable access has no ownership check.
- **Fix:** Thread `user_id` (from auth stub / `local` default) through all repo getters now, so the seam exists before auth does; or correct the doc to "single-user, no isolation" and add the seam as tech debt with an ADR. Implement the missing `GET /versions/:id` or remove it from docs.
- **Validation:** Test asserting cross-`user_id` fetch denied once the parameter exists; contract test for the versions route.

### H11 — Queue-limit check is TOCTOU-raced and excludes sync jobs

- **Category:** Reliability / API
- **Severity:** High
- **Location:** `backend/alphalab_api/routes_runs.py:59-64`.
- **Evidence:** `queued_depth() >= limit` then `create_job` in separate sessions, non-atomic; sync jobs never counted.
- **Fix (with C2/C3):** Atomic `INSERT ... WHERE count < limit` or a job-guard transaction; count sync jobs during execution.
- **Validation:** Concurrent-burst test asserting depth never exceeds limit.

### H12 — Engine guesses multi-output channel when validation is bypassed [IMPLEMENTED]

> **Implementation note (2026-09-09):** Fixed without an engine version bump (valid-spec behavior is bit-identical; the old path only triggered on specs the validator already rejects, so no stored run could have exercised it). `_Evaluator.operand` now raises `ValueError` when a multi-output indicator lacks `output`, or when the named output does not exist — stdlib exception to preserve `alphalab_core` purity (no contracts import). Changed: `backend/alphalab_core/engine.py`. Added `test_missing_output_selector_raises` (Donchian(2), warm after 1 bar so the operand is really evaluated; asserts both missing and bogus selectors raise). Validated: engine+purity suites green; full backend suite 119 passed (excl. perf), confirming templates/specs with proper selectors are unaffected.

- **Category:** Backtesting Correctness
- **Severity:** High
- **Location:** `backend/alphalab_core/engine.py:89-92` (`_Evaluator.operand`: `output or next(iter(ref.values))`); contract in `docs/strategy-spec.md:66-67`; validator rejects it at `strategy.py:163-170` but `run_backtest` is directly callable.
- **Evidence:** MACD/BB/Donchian condition without `output` silently trades the wrong series (dict order = `macd`/`upper`) whenever `validate_spec` is skipped (all unit tests call the engine directly).
- **Why it matters:** Backtest-invalidating defense-in-depth gap: any future caller that skips validation gets a plausible-but-wrong strategy.
- **Fix:** Raise `StrategyInvalidError("missing output selector")` in the engine instead of guessing; add test calling engine without validation.
- **Validation:** Test asserting raise on missing `output` for multi-output indicators; existing validated paths unaffected.

### H13 — Zero property tests despite an explicit mandate (no-lookahead/determinism unenforced)

- **Category:** Testing
- **Severity:** High
- **Location:** `backend/tests/*.py` (no `hypothesis` import anywhere) vs `docs/testing.md:13-18`, `requirements-dev.txt:3`.
- **Evidence:** Content search confirms zero usage; the mandated accounting-identity, determinism-hash, no-lookahead future-mutation, reversal-conservation, patch-atomicity, numpy causal-window fuzz tests do not exist.
- **Why it matters:** The highest-value engine guarantees have no automated enforcement; regressions in lookahead/determinism will not be caught.
- **Fix:** Add `test_properties.py` with at minimum: (1) future-bar mutation invariance (append/modify bars after signal window → earlier trades unchanged), (2) determinism (same inputs → identical `resultHash` 50×), (3) accounting identity (cash + open equity == initial + realized + unrealized − fees), (4) reversal conservation.
- **Validation:** `make test` runs them; mutation-testing spot check (inject a lookahead, watch the test fail).

### H14 — Required hand-computed run fixtures absent (money-path coverage is ad hoc)

- **Category:** Testing
- **Severity:** High
- **Location:** `backend/tests/fixtures/` (only `indicators/golden_60.json` + `templates/*.json`) vs `docs/testing.md:14` (`fixtures/runs/*.json`: win, loss, exact-touch, ambiguous, gap, capital-skip, reversal, trailing, spread-side…).
- **Evidence:** Directory listing; `test_engine.py` (~300 lines) covers cases inline but several mandated fixtures have no dedicated test.
- **Fix:** Create the enumerated fixture tier, each with hand-computed trades/metrics in cents; wire them as parametrized golden tests.
- **Validation:** Each fixture asserts exact cents with zero tolerance; CI runs them.

### H15 — Backend dependencies unpinned, no lockfile (reproducibility promise undermined)

- **Category:** DevOps / Reproducibility
- **Severity:** High
- **Location:** `backend/requirements.txt:1-6`, `requirements-dev.txt` (floor-only pins); no `requirements.lock`/`uv.lock` (only `web/package-lock.json` exists).
- **Evidence:** `numpy>=1.26`, `pydantic>=2.0`, … resolve different trees over time; `engineVersion` does not capture the numpy version.
- **Why it matters:** Reproducibility issue: same spec+data can produce different indicator floats after an upgrade, while `resultHash` claims identity.
- **Fix:** Pin exact versions + add lockfile (`uv.lock` or `pip-compile`); record dependency versions in run metadata; frontend already fine (`npm ci` + lockfile).
- **Validation:** Clean-install reproducibility test; CI asserts lock freshness.

### H16 — CI omits three of its four documented gates

- **Category:** DevOps / Testing
- **Severity:** High
- **Location:** `.github/workflows/ci.yml:1-56` vs `docs/testing.md:3-10`.
- **Evidence:** No contract-equivalence (Pydantic⇄Zod) job, no web money-keyword grep-gate, no migration check (`alembic heads` linearity); three alembic versions (`0001-0003`) with nothing asserting heads. No Docker files (localhost `make dev-*` only).
- **Fix:** Add the three jobs; assert single alembic head; document the no-Docker decision or add a minimal image.
- **Validation:** CI red on intentional drift (schema-only change, money keyword in `web/`, branched migration).

---

## 3. Medium findings

### M1 — `spreadMaxBps` is a static kill-switch, not a per-bar filter

- **Category:** Trading Logic
- **Severity:** Medium
- **Location:** `backend/alphalab_core/engine.py:267-268`; `backend/alphalab_core/config.py:28-31`; doc `docs/backtest-engine.md:5`.
- **Evidence:** Compares per-run constant `costs.spread_bps` against `spread_max`, so it blocks all or no bars; users expect illiquid bars skipped.
- **Why it matters:** Research-misleading: users believe a liquidity filter is active.
- **Fix:** Either remove the filter (schema-reject + doc update) or implement genuine per-bar spread (requires spread series in dataset — larger change; prefer removal in MVP).
- **Validation:** Test asserting reject-or-filter behavior matches docs.

### M2 — Sizing + notional cap use signal-bar estimate, not fill; cash checked before entry commission

- **Category:** Trading Logic / Risk
- **Severity:** Medium
- **Location:** `backend/alphalab_core/engine.py:379-412` (`open_position`: `entry_est=close[sig]±spread/2`, `fill=open[bar]±spread±slip`, cap at `:406` on estimate, cash check at `:406` before `:412` commission).
- **Evidence:** Gap-up fill can breach `maxNotionalMult`/`leverageMax` unchecked; entry estimate omits slippage so `intended_risk` is systematically optimistic by `slip*price*qty` (only warned if >20% at `:432-434`).
- **Fix:** Re-check cap against realized `fill` (downsize or skip + warn `notionalCapFill`); include slippage in `entry_est` or document the bias; deduct commission before the cash-sufficiency check.
- **Validation:** Gap-fill sizing test; slippage-inclusive intended-vs-realized risk assertion.

### M3 — Equity omits accrued exit costs (intra-trade equity/drawdown flattered)

- **Category:** Backtesting Correctness
- **Severity:** Medium
- **Location:** `backend/alphalab_core/engine.py:560-567`; formula in `docs/backtest-engine.md:86`; affects `metrics.py:58-78` drawdown.
- **Evidence:** `unrealized=(c-entry)*qty` on raw close; `cash` net of entry commission only; doc formula says `-accruedCosts`.
- **Fix:** Subtract estimated exit spread/slip/commission from unrealized; disclose the estimator in assumptions.
- **Validation:** Single-trade equity-path test vs hand-computed accrued-cost path.

### M4 — Cold-start safety lives outside the engine (direct callers seed from `startTime`)

- **Category:** Reproducibility / Backtesting Correctness
- **Severity:** Medium
- **Location:** `backend/alphalab_core/engine.py:175-180` (no `coldStart` warning); warning only in `service.py:197-199`.
- **Evidence:** Direct `run_backtest` callers (tests, perf, scripts) silently seed EMA/Wilder from `startTime`, violating the `AGENTS.md` warmup rule.
- **Fix:** Move warmup-sufficiency check into the engine (require `warmupBars` of history before first signal or emit `coldStartAssumed` warning in-run).
- **Validation:** Test calling engine with too-short history asserts warning/skip.

### M5 — API/doc contract drift (client-breaking)

- **Category:** API
- **Severity:** Medium
- **Location:** `docs/api.md:13,33,48-49,60` vs `routes_runs.py:60`, `routes_ai.py:68,100-102,272-282`, sweep response shape.
- **Evidence:** `Idempotency-Key` never read; 429 without `retryAfterMs`; `quota.remainingToday` returned as `quota.note` string; `strictProvider: gemini` has no such request field; sweep returns `jobs|runs` vs documented `runIds`; `GET /api/versions/:versionId` unimplemented.
- **Fix:** Implement-or-remove per item; add OpenAPI/contract tests asserting documented fields.
- **Validation:** Contract test suite replaying `docs/api.md` examples.

### M6 — Full-table loads for pagination/bars (OOM on large datasets)

- **Category:** Performance / Database
- **Severity:** Medium
- **Location:** `routes_runs.py:123-130` (trades load-all-then-slice), `routes_catalog.py:193-199`, `repos.py:132-138` (bars, no limit), `list_strategies`/`list_datasets` unbounded (`routes_catalog.py:70-76,155-164`).
- **Evidence:** A 2M-bar dataset (~150MB per `persistence.md:66`) loads per request × concurrency.
- **Fix:** SQL `LIMIT/OFFSET` + keyset pagination; server-side downsampling with `MAX`/`MIN` aggregation; cap bars endpoint with documented default.
- **Validation:** Large-dataset pagination test with query-count/memory assertions.

### M7 — Promised index `trades(run_id, exit_bar)` missing; `backtest_runs.job_id` unindexed; N+1 in experiment load

- **Category:** Database
- **Severity:** Medium
- **Location:** `models.py:92,112`; promise in `persistence.md:57`; N+1 in `routes_runs.py:228-234`.
- **Evidence:** `run_id` index only; ordering by `exit_bar` sorts unindexed; `job_id` plain column; experiment loads one `get_run` + one `get_strategy_version` per member.
- **Fix:** Migration adding composite index + `job_id` index; batch-load experiment members (`WHERE id IN (...)`).
- **Validation:** `EXPLAIN QUERY PLAN` test; experiment load query-count test.

### M8 — Timeout message hardcodes 120s; orphan worker keeps writing progress after timeout

- **Category:** Reliability
- **Severity:** Medium
- **Location:** `jobs.py:130-134` vs `settings.job_timeout_s`; `worker.py:38-49`.
- **Evidence:** `"timeout: run exceeded 120s"` literal; orphan process keeps `report_progress` after the waiter cancelled (only run-persist guarded at `jobs.py:141-149`).
- **Fix:** Interpolate `settings.job_timeout_s`; guard `report_progress` with terminal-state check / generation counter.
- **Validation:** Timeout test with custom setting asserting message + no post-timeout progress writes.

### M9 — Sync runs uncancellable and untimed

- **Category:** Reliability
- **Severity:** Medium
- **Location:** `jobs.py:178-208` (no `should_cancel`/timeout wiring); `DELETE /jobs/:id` 409s correctly but heavy sync runs block workers.
- **Evidence:** Async path polls DB cancel every 1k bars; sync has nothing.
- **Fix (with C2):** Route heavy sync through the cancellable worker or add cooperative cancel checks.
- **Validation:** Cancel-during-sync test.

### M10 — AI `propose`/`explain`/`summarize` grounding, caching, and DoS gaps

- **Category:** AI Integration / Security
- **Severity:** Medium
- **Location:** `routes_ai.py:68,100-102,138-140,156-160,188,210-212,240,265,272-282`; `gemini.py:101-106,119-121`; `ruled.py:16-55`; `repos.py:283,320`.
- **Evidence:** (a) `propose` without `strategyVersionId` records `validation.ok=True` without validating; (b) `intent` unbounded → regexes over multi-MB text before 1000-char truncation (CPU/memory DoS); (c) `explain` has no grounding check and hallucinated citations cache 30 days; (d) `summarize` grounding checks key membership, not values; (e) fallback cache-key mismatch means Gemini→ruled fallback never hits (`(gemini,flash)` lookup vs `(ruled,ruled/1.0)` store); (f) `confirm` catches only `PatchError`, mis-mapping validation failures away from `AI_VALIDATION_FAILED` + skipping `rejected` bookkeeping.
- **Fix:** Enforce max intent length (e.g., 4k chars) at the route; validate-or-mark-`incomplete` for missing-version proposes; value-level grounding (parse cited numbers, compare); unify cache keys on `(provider, model)` actually used; widen `confirm` exception mapping.
- **Validation:** Per-item tests: oversize intent 400/413; missing-version propose never `ok`; fallback cache-hit test; hallucinated-number rejection test.

### M11 — CSV caps checked after full body buffered; `rows_rejected` unbounded; raw cells in errors

- **Category:** Security / Performance
- **Severity:** Medium
- **Location:** `alphalab_marketdata/__init__.py:70,112-127,167-176`; `routes_catalog.py:143`.
- **Evidence:** 25MB/2M-row caps enforced after FastAPI parsed the whole `csvText` JSON string; `manifest.rows_rejected` appends per bad row unbounded (giant JSON column); `filename` verbatim unbounded; `_parse_time` embeds raw cell `{raw!r}` into stored manifest.
- **Fix:** Request-size limit at middleware; cap `rows_rejected` (e.g., first 100 + count); truncate `filename`; sanitize cell echoes.
- **Validation:** Oversize/many-bad-row import tests asserting bounded manifest + 413 behavior.

### M12 — Codegen hardcodes 3 of 8 enum lists (schema-drift gate has a hole)

- **Category:** Architecture / DevOps
- **Severity:** Medium
- **Location:** `backend/scripts/codegen.py:30-33` vs `shared/schemas/strategy.spec.json`; CI gate `.github/workflows/ci.yml:44-47`; related `conditions.ts:31-35` (`Date.now()` ids) vs `canonical.py:20-30` (ids not stripped → identical trees hash differently).
- **Evidence:** `indicator_kinds`, `price_fields`, `exit_kinds` are literals; gate only detects drift in five schema-read lists.
- **Fix:** Read all lists from the schema; strip volatile `id` fields in canonical hashing or make builder ids deterministic.
- **Validation:** Schema-addition test asserting generated enums update; hash-equality test for id-only differences.

### M13 — Hash-normalization gaps break economic-identity dedupe

- **Category:** Reproducibility
- **Severity:** Medium
- **Location:** `service.py:119` (`initialCapital` verbatim); `canonical.py:18-27` (Decimal→round-6); `marketdata:167-172` (full float repr).
- **Evidence:** `"10000"` vs `"10000.00"` hash differently; sub-1e-6 trade differences merge while 1e-12 bar noise forks. Byte-determinism holds; economic dedupe does not.
- **Fix:** Normalize money inputs through `Decimal` before hashing; document the two-tier (exact dedupe vs economic equality) semantics.
- **Validation:** Hash-equality tests for money spellings; sensitivity tests both directions.

### M14 — Settings mostly not env-overridable; URLs/ports hardcoded; Launcher ships unvalidated numbers

- **Category:** Configuration / Frontend
- **Severity:** Medium
- **Location:** `settings.py:11-35` (only `ALPHALAB_DB`, `ALPHALAB_AI_PROVIDER` read); `web/vite.config.ts:10`; per-script `BASE` constants; `Launcher.tsx:54-63` (`Date.parse`→`NaN`→`null`, `Number("")===0`, raw string capital/slippage).
- **Evidence:** Operators cannot tune thresholds/concurrency without code edits; typos round-trip as confusing server errors.
- **Fix:** Read all settings from env with `ALPHALAB_` prefix + add `.env.example`; centralize API base URL; add client-side date/number validation with ranges.
- **Validation:** Env-override test; Launcher test with empty/invalid inputs asserting inline errors, no request sent.

### M15 — SSE stream uncapped; queued jobs never recovered after restart

- **Category:** Reliability
- **Severity:** Medium
- **Location:** `routes_runs.py:158-176` (0.5s DB poll/forever, fresh session per tick); `repos.py:186-194` (only `running` healed); `routes_runs.py:65-66` fire-and-forget.
- **Evidence:** N tabs = N poll loops; `queued` jobs (incl. tasks killed by shutdown) stay queued, inflating depth (feeds C3).
- **Fix (with C3):** SSE idle/absolute timeout + backoff; recover stale `queued` on startup; track task handles for graceful shutdown.
- **Validation:** Idle-SSE disconnect test; restart-recovery test for `queued` rows.

### M16 — Dedupe poisons valid row if first duplicate is invalid

- **Category:** Market Data
- **Severity:** Medium
- **Location:** `alphalab_marketdata/__init__.py:138-154` (`seen.add(ts)` before problems check).
- **Evidence:** Invalid first occurrence reserves `ts`; later valid same-`ts` row counted `duplicates_dropped` and lost.
- **Fix:** Mark seen only on store; add test with invalid-then-valid same timestamp.
- **Validation:** Import test asserting the valid row survives + correct counters.

### M17 — Patch bypasses every numeric range (negative risk flows to silent skip)

- **Category:** Validation / Trading Logic
- **Severity:** Medium
- **Location:** `patch.py:104-128` vs ranges in `strategy.spec.json:53-193` + `strategy.py`; consumer `engine.py:399` (`qty_raw=risk_cash/dist` → negative qty → `skipped_min_qty`).
- **Evidence:** `setParam/setRisk/setExits` assign raw values; relies entirely on caller re-validation.
- **Fix:** Validate ranges inside `apply_patch` (or make it return the patched spec and force `validate_spec_or_raise` in the same call); engine should raise on non-positive qty instead of silently skipping.
- **Validation:** Patch tests with negative/out-of-range values asserting rejection; engine test asserting raise on negative qty.

---

## 4. Low findings

### L1 — Sharpe gate off-by-one (`101` vs documented `100`)

- **Category:** Performance Calculations
- **Severity:** Low
- **Location:** `metrics.py:98` vs `docs/results-experiments.md:32`.
- **Fix:** Align code and doc (recommend `>= 100` per doc); add boundary test at exactly 100 bars.

### L2 — `maxNotionalMult` ceiling contradicts spec doc; defaults violate the doc

- **Category:** Documentation / Validation
- **Severity:** Low
- **Location:** `strategy.spec.json:190-191` (≤30) vs `docs/strategy-spec.md:37` (≤5) vs `templates.py:52-63` (default 10).
- **Fix:** Pick one ceiling, update all three + error message; add equivalence test.

### L3 — Frontend a11y gaps (keyboard, screen reader, live progress)

- **Category:** Frontend
- **Severity:** Low
- **Location:** `RunView.tsx:88` (`<tr onClick>` no keyboard role), chart/heatmap containers (`charts.tsx:100,135,157`, `MonthlyHeatmap.tsx:6`), tables without captions, nav without `aria-current` (`App.tsx:57-69`), job progress without `aria-live` (`Launcher.tsx:205-210`).
- **Fix:** Keyboard handlers + roles, `role="img"`/`aria-label` on charts, captions, `aria-current`, `aria-live` on progress.
- **Validation:** axe/Vitest a11y checks + keyboard walkthrough.

### L4 — Indicator edge robustness (VWAP/ADX/EMA NaN handling, trailing ATR timing, session truncation)

- **Category:** Backtesting Correctness (minor)
- **Severity:** Low
- **Location:** `indicators.py:33-35,184-188,219-221`; `engine.py:153-157,257-259,542-545`; `marketdata/__init__.py:175-176`; `strategy.py:199-207,244-256`.
- **Evidence:** VWAP NaN inflates `warmupBarsSkipped`; ADX forward-fills across NaN DX; `_ema_series` NaN poisons tail; trailing uses close-based `ATR[i]` intrabar; session hour truncation coarse for M5/M15.
- **Fix:** NaN-veto (no signals on stale indicator bars), NaN-reset in EMA, disclose trailing-ATR timing in assumptions, document session-hour semantics (already in `market-data.md:31` — keep, add UI hint).
- **Validation:** Unit tests per edge with crafted NaN/zero-volume series.

### L5 — Web tests cover only pure helpers; backend live/probe scripts untested and repo-polluting

- **Category:** Testing / Code Quality
- **Severity:** Low
- **Location:** `web/src/*.test.ts` (~83 lines, helpers only); `backend/scripts/probe_gemini.py:7-10` (subprocess key pull into env), `smoke_live.py:78` (writes `.smoke_ids.txt` to repo root), `proof_trades.py` (unguarded `trades[0]`), `gemini_live.py`/`diag_*` shadow logic.
- **Fix:** Add component/API/chart tests (error mapping, `normalize` zero/negative, SSE fallback, `buildSpec`); move script outputs to temp dir; guard/retire probe scripts; never pull keys via subprocess.
- **Validation:** `make test-web` covers the H3–H5 fixes; `git status` clean after script runs.

### L6 — Assorted small gaps (dead field, hash sensitivity, synthetic footguns, `const offset`, session-on-H1, metrics presentation)

- **Category:** Code Quality (with minor research-presentation notes)
- **Severity:** Low
- **Location:** `engine.py:160-200` (`execution.fillBasis` never read); `canonical.py:18-27` + `runs.py:51-63` (dust-insensitive, trades-only hash); `synthetic.py:28-40` (no grid check, `with_volume=False` default); `engine.py:79-80` (`const` ignores offset); `strategy.py:199-207` vs `strategy-spec.md:96` (session on H1); `metrics.py:33-34,60-94` (terminal-underwater `avgDrawdown=None`, breakevens depress win-rate); `format.ts:26-33` (`normalize` hides scale, zero-start → zeros); `charts.tsx:68-92` (second-truncation, unsorted/miscolored markers); `format.ts`/`MonthlyHeatmap` rounding (covered in H3).
- **Fix:** One cleanup pass: assert `fillBasis == next_open` in engine (fail loudly if schema relaxes); document hash-sensitivity intent; add grid-alignment assert + explicit volume flag in synthetic callers; raise on `const`+offset in engine (defense in depth); align session-timeframe rule; document metrics edge semantics in UI footers; sort markers, fix exit colors, avoid second-truncation.
- **Validation:** Unit tests per sub-item; UI snapshot for markers/footers.

---

## 5. Optional improvements

### O1 — No vulnerability scanning; backend CI runs the slow perf test on every push

- **Category:** DevOps
- **Severity:** Optional
- **Location:** `.github/workflows/ci.yml:24` (`test_perf.py` 100k-bar/30s budget inline); no `pip audit`/`npm audit`/Dependabot.
- **Fix:** Split perf into nightly/scheduled job; add `pip audit` + `npm audit` + Dependabot config.
- **Validation:** CI timing improvement; audit step green.

### O2 — AI citations fetched but dropped in UI; `TimeoutError`/`TooManyTrades` UX unrefined

- **Category:** Frontend / AI
- **Severity:** Optional
- **Location:** `AiPanel.tsx:43-53` (ignores `out.citations`); sweep/large-run error paths.
- **Evidence:** Server grounding exists but the user cannot audit cited metric ids (`docs/frontend.md:15` contract unverifiable in UI).
- **Fix:** Render citation chips + provider/model/token footer (already partially present); add dedicated large-run/timeout guidance UI.
- **Validation:** Component test with citations payload.

---

## 6. What was checked and found sound (no finding)

- **No lookahead in the main signal path:** signals evaluated on closed bar `t` (`decided(i-1)`), fills at open `t+1` — correct structure; findings above are edge-case deviations, not a broken core.
- **Stop-first ambiguity rule:** implemented and counted (`ambiguousBars`) — sound; gap pricing around it is the gap (C1).
- **Decimal money math:** cash/fees/notional in `Decimal`, exact-cent tests — sound; presentation layer (H3) is where exactness is lost.
- **Core purity:** `alphalab_core` within stdlib+numpy — holds per reviewed imports.
- **No `eval`/`exec` on AI output; strategy-as-data** — confirmed.
- **No SQLi** (ORM + `?` placeholder in worker) **and no SSRF via CSV** (text-only import) — confirmed.
- **No XSS sink** (`dangerouslySetInnerHTML`/`innerHTML` zero hits; `AiPanel` uses escaped `{m.text}`) — residual risk is prompt-injected text + future Markdown rendering.
- **Seed data committed and regenerable** (`data/samples/` + seeded `gen_samples.py`) — sound.
- **Type strictness genuinely on** (`tsconfig` strict + `mypy.ini` strict) — sound.

---

# Recommended Implementation Order

Dependency-aware; backtest correctness first because every stored run predating those fixes is suspect.

**Phase 0 — Stop the bleeding (deploy/reliability blockers)**
1. C7 `httpx` to prod requirements + lazy import (unbreaks AI surfaces).
2. C6 single engine/session factory + SQLite busy-timeout (stops flaky failures).
3. C2 sync-path concurrency gating + timeout (stops DoS/threadpool exhaustion).
4. C3 sync-failure job finalization + stale-`queued` recovery (with M15 SSE/recovery).
5. C5 shared Pydantic request validation for run + sweep (kills 500s and negative-cost P&L).

**Phase 1 — Backtest correctness (invalid-result fixes; re-hash affected golden runs)**
6. C1 gap-through-stop adverse-open pricing + `gapThroughStop` warning.
7. H1 end-of-data exit costs.
8. H2 both-fire tie-break symmetry + doc update.
9. H12 engine raises on missing multi-output selector.
10. M2 sizing/cap on realized fill + slippage-inclusive estimate.
11. M3 accrued exit costs in intra-trade equity.
12. M4 in-engine warmup/cold-start guard.
13. M16 dedupe ordering; M17 patch range validation (fail loudly, never silent-skip).
14. L1/L2/L4/L6 small correctness cleanups (Sharpe gate, ceilings, NaN vetoes, markers).

**Phase 2 — Security hardening (after math is right)**
15. H8 header-auth for Gemini key + log redaction.
16. H7 typed client errors (no internal text in `job.error`/SSE).
17. H9 token-budget ledger + truthful quota API.
18. H10 `user_id` seam through repo getters (or corrective ADR + doc fix).
19. H11 atomic queue guard; M10 AI validation/grounding/cache fixes; M11 CSV/error boundedness.

**Phase 3 — Data/perf scale**
20. M6 SQL pagination + server downsampling; M7 composite/job indexes + batch experiment load.
21. H6 semaphore scope narrowing (with C6/C2); M8 timeout message + progress guard; M9 sync cancel.

**Phase 4 — Guarantee enforcement (testing + supply chain + CI)**
22. H14 hand-computed run fixtures (exact cents).
23. H13 hypothesis property suite (future-mutation, determinism, accounting identity).
24. H15 pinned backend deps + lockfile + version-in-run-metadata.
25. H16 three missing CI gates; M12 full-schema codegen; M13 hash normalization docs/tests.

**Phase 5 — Frontend correctness + UX**
26. H3 server-only metrics rendering + `fmtMoney` string-based formatting.
27. H4 per-field validation details in forms.
28. H5 loading/error/retry states + bars-query gating + Compare fault isolation.
29. M14 env-overridable settings + `.env.example` + Launcher pre-validation.
30. L3 a11y pass; L5 web component tests; O2 citation/quota UI.

**Phase 6 — Optional**
31. O1 perf-test split + security scanning + Dependabot.

**Post-fix diligence:** after Phase 1, disclose hash changes (old `resultHash` values for affected scenarios were computed under the buggy rules), rebuild golden vectors, and add an ADR noting which historical runs are not comparable to new runs. After Phase 2, rotate any Gemini key that may have been logged in URLs.
