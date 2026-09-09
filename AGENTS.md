# AGENTS.md — Working agreement for implementation agents

Read before writing code: `PROJECT_BRIEF.md` → `ARCHITECTURE.md` → relevant `docs/*.md` → relevant `docs/adr/*` → existing code/tests.

## 1. Source-of-truth hierarchy

1. Explicit user instruction in this session
2. `PROJECT_BRIEF.md` (product)
3. `ARCHITECTURE.md` (system — wins over specs on conflict unless ADR overrides)
4. `docs/adr/*` (why)
5. `docs/*.md` specs (contracts)
6. Existing code/tests
7. Your judgment for ordinary details

Conflict? Stop, surface it, do not silently pick one.

## 2. Non-negotiable invariants

- `backend/alphalab_core` is **pure Python** (stdlib + numpy only): no `fastapi`, `sqlalchemy`, `httpx`, `google.generativeai` imports. Purity test enforces this. Violation = reject the change.
- Money math lives **only** in `alphalab_core` (`Decimal` for cash/fees/notional). `web/` never computes P&L, equity, metrics (grep-gate outside `formatters/`).
- Strategy changes go through `shared/schemas/strategy.spec.json` first: edit schema → regenerate Pydantic + Zod → equivalence test green. Never add a field in one language only.
- Completed rows (`strategy_versions`, `datasets`, `backtest_runs`) are **immutable** — updates must fail; create new versions.
- AI output is **untrusted**: must pass Pydantic schema validation + grounding check and (for strategy changes) explicit user confirmation before it becomes a new `StrategyVersion`. Raw model text never applied.
- Determinism: same `(specHash, datasetHash, configHash, engineVersion, instrumentMetaVersion)` → identical result hash. Any nondeterminism is a P0 bug.
- No lookahead: signal at bar `t` may only use bars `≤ t`; fills no earlier than open `t+1`. No vectorized signal shifts (`shift(-1)` etc.) — explicit index loop only. Indicators seed from the warmup lookback (`warmupBars = max(3×maxPeriod, 50)`), never from `startTime`. When in doubt, choose the **pessimistic** fill and disclose it.
- Money in `Decimal`/TEXT; market bars may be REAL. Float `==` uses epsilon `1e-9`; crosses need t and t−1 non-warmup.

## 3. Boundaries

```text
alphalab_core → stdlib + numpy only
alphalab_api / store / ai → never contain engine math; api orchestrates core
web/ → renders server data only; Zod schemas generated, not hand-diverged
```

- No financial logic in route handlers or React components — thin orchestration + rendering only.
- No new top-level deps without noting in PR: why needed, alternatives, license, size. Prefer stdlib.
- No microservices, no Redis/Celery, no broker code, no paid-AI requirement in MVP. Gemini is BYOK free-tier with ruled fallback — core works with no key.
- Never log or persist Gemini API keys (OS keyring/env only).

## 4. How to work

- Build in the order in `ARCHITECTURE.md §12`: contract → strategy → data → indicators → engine → metrics → api/jobs → ai (ruled first, then Gemini) → web.
- Vertical slices, small diffs, repo green after each slice (`make test` + `make typecheck`).
- Money tests use **small hand-computed fixtures** (see `docs/testing.md`): exact cents, no tolerances on accounting.
- Every engine-affecting change needs: pytest unit + golden vector (if indicators/metrics) + hypothesis determinism/no-lookahead properties.
- Every schema change needs: shared-schema edit + codegen + equivalence test + both-side validation tests.
- Every AI change needs: replay-fixture test (no live key) + grounding-failure test + fallback test.
- If the spec is wrong, update the spec + ADR (if architectural) in the same change. Never let code and docs diverge silently.
- MVP scope cuts in `ARCHITECTURE.md §8` are binding. Do not "helpfully" add partials, pyramiding, limit orders, live providers, or walk-forward optimizer. Schema fields for them must reject with `NOT_SUPPORTED_IN_MVP`.

## 5. Commands (repo root)

```bash
make dev-api    # uvicorn alphalab_api --localhost:4100
make dev-web    # vite dev (proxies /api)
make codegen    # shared/schemas → pydantic + zod
make test       # pytest (backend) + vitest (web) + contract-equivalence
make test-core  # pytest backend/alphalab_core only — must always pass
make typecheck  # mypy/pyright (backend) + tsc --noEmit (web)
make migrate    # alembic upgrade head
```

Paths: samples in `data/samples/`, migrations in `backend/alphalab_store/migrations/`, fixtures in `backend/tests/fixtures/`, shared schema in `shared/schemas/strategy.spec.json`.

## 6. Definition of done (per slice)

- [ ] Implements the spec contract (request/response, errors, state transitions)
- [ ] Tests: happy path + invalid input + boundary (empty data, single bar, gap, exact stop-touch)
- [ ] Determinism: repeated run → identical hash
- [ ] Errors are typed (backend `errors.py`, web maps codes), actionable, logged without secrets
- [ ] Docs updated if contract changed; ADR added/updated if decision changed
- [ ] No authoritative numbers in web; no AI in money path; no key in logs/DB

## 7. What not to do

- Do not execute AI-generated or user-supplied code (`eval`, `exec`, dynamic import of user strings). Strategy is data, never code.
- Do not "improve" fills to look better (e.g., filling at signal-close instead of next-open). Realism > attractive equity curves.
- Do not invent metrics or annualization constants — use `docs/results-experiments.md` formulas exactly.
- Do not add auth complexity (OAuth, JWT infra) — MVP is localhost single-user with `user_id` reserved (see `docs/security.md`).
- Do not add a Node backend service, Next.js migration, or Celery/Redis without an ADR — the polyglot shape is decided (ADR 0009) and changes go through it.
- Do not run the engine on the event loop or rely on in-memory cancel flags (see `docs/backtest-engine.md §10`): sync = threadpool, async = process pool, cancel = DB flag polled every 1k bars.
- Do not allow `eval`-style float equality (`==`) in conditions — epsilon `1e-9` only; and never seed indicators from `startTime` (warmup lookback only).
