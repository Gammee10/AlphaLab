# Testing strategy

## Gates (CI must run all four)

```bash
make test-core   # pytest backend/alphalab_core only — deterministic, no FS/network — must be 100% pass
make test        # pytest (backend) + vitest (web) + contract-equivalence (Pydantic⇄Zod)
make typecheck   # mypy/pyright (backend) + tsc --noEmit (web)
make purity      # banned-import scan: fastapi/sqlalchemy/httpx/generativeai in alphalab_core; money keywords in web/ outside formatters/
```

## Core test tiers (engine correctness is the product)

1. **Hand-computed money fixtures** (`backend/tests/fixtures/runs/*.json`): tiny bar series (4–20 bars) with manually calculated fills/P&L/equity/fees. Assert **exact cents** — zero tolerance on accounting. Minimum fixtures: basic win, basic loss, stop-exact-touch, target-exact-touch, ambiguous-bar (both touched → stop), gap-through-stop, gap-risk-exceeded warning (>20%), capital-skip, min-qty-skip, pyramid-skip (same-direction signal while open → ignored order row), reversal-two-legs (opposite signal → close + open at same open, two commissions), time-stop, trailing-ratchet-never-loosens + activationR gating, opposite-signal exit timing, commission+slippage stacking, spread-side precision (long exits at bid).
2. **Golden indicator vectors** (`backend/tests/fixtures/indicators/*.json`): EMA/RSI/ATR/MACD/BB/ADX/Donchian outputs on a fixed 60-bar series (tolerance 1e-9, documented per indicator; money tests built on indicators still exact because qty/price rounding happens after). Plus cold-start test: run over truncated history must equal run over full history with lookback (same signals in overlap window).
3. **Property tests** (hypothesis): accounting identity (`Σ trade net == finalEquity − initial − openPL`), determinism (same inputs → same `resultHash` across 2 runs), no-lookahead (shifting future bars must not change fills at `t`; mutation test: corrupt bar `t+5`, assert trades closing ≤ `t` unchanged), reversal conservation (every close leg has a matching order row), patch atomicity (`apply_patch` with one bad op leaves spec unchanged). Numpy kernels additionally fuzzed for causal-window violations.
4. **Validation tests:** every rule in `docs/strategy-spec.md` has a reject-case; `reservedForFuture` non-empty → `NOT_SUPPORTED_IN_MVP`; group depth 4 → reject; 13th leaf → reject; `==` epsilon boundary case; **VWAP on volume-less FX dataset → `DATASET_INVALID`**; **session window on H4/D1 → reject with explanation**.
5. **Metric tests:** known-trade-list → exact metric values incl. null cases (N=0, no losses, N<30 Sharpe null, sd=0 Sharpe null, <100 bars Sharpe null).

## API/store tests

- Contract tests per `docs/api.md` route (happy + invalid + boundary: empty CSV, single-bar dataset, gap manifest, exact stop-touch run).
- Immutability tests: UPDATE `strategy_versions`/`datasets`/`backtest_runs` must abort (trigger check).
- Job tests: sync/async threshold, cancel (DB flag honored within 1k bars), timeout (worker killed → zero partial rows), sweep cap (33rd combo rejected), crash recovery (kill mid-run → no partial run rows; stuck `running` → `failed/restarted` on boot), idempotent resubmit (same dedupe key → `deduped: true`, one run row), **idempotency race** (two concurrent identical submissions → one run, loser returns winner `deduped: true`, no 500), **event-loop liveness** (200k-bar async run in progress → `/api/templates` responds < 200ms), cross-host determinism (same fixture in-process vs spawned subprocess → identical `resultHash`), import-safety (spawned `alphalab_core` import has no side effects).

## AI tests

- RuleBasedAssistant: intent → expected ops fixtures ("change stop to 1.5 ATR", "add volatility filter", gibberish → zero-op clarifier).
- Gemini adapter (no live key): replay fixtures (recorded JSON responses) → validated `StrategyPatch`; grounding-failure (invented metric) → `AI_VALIDATION_FAILED`; stale `baseSpecHash` confirm → rejected; quota-429 fixture → fallback to ruled with `fallbackReason: quota`.
- Contract: every propose/explain/summarize test asserts the `provider/model/tokens/citations` footer fields exist.

## Data tests

- CSV edge: BOM, CRLF, tz offsets, dup rows, bad OHLC row, misaligned grid time, 2M+1 rows.
- Timezone: session filter stable across DST switch dates (UTC construction).

## Performance smoke

- 500k-bar H1 run completes < 10s on reference laptop (CI records duration; regression > 2× fails). No micro-benchmarks in MVP.
