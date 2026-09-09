# ADR 0009 — Polyglot stack: Python (FastAPI) backend + TypeScript (React/Vite) frontend

## Status
Supersedes the earlier single-language TypeScript decision (v1). Reason: explicit user direction toward a Python+TypeScript polyglot, re-evaluated on merits below — the polyglot is justifiable for this product, with conditions.

## Context
AlphaLab needs: (a) a correctness-critical numerical core (indicators, event-ordered simulation, accounting); (b) a schema-strict API with jobs and persistence; (c) a fast-iterating research UI; (d) AI orchestration (prompt packing, retries, quota handling) that in practice is cleaner in Python; (e) localhost-first ops with minimal burden. The original ADR chose single-language TypeScript for toolchain simplicity. The user asked to revisit with a React/Next.js + FastAPI (+ Node where it earns its place) polyglot.

## Options evaluated (seriously, with scenarios)

### A) Single-language TypeScript (previous decision)
- Engine, API, UI in one language/toolchain (Node 20, Fastify, Vitest, React/Vite).
- Pros: one runner, no cross-language schema drift, trivial onboarding, lint-enforced purity of `core`.
- Cons: no numpy/pandas/pytest-hypothesis ecosystem; quant hiring pool skews Python; AI SDK patterns and structured-output helpers mature faster in Python; hand-rolled indicators required either way, but Python's `decimal` + `numpy` testing idioms are battle-tested for finance.
- Verdict: valid, lowest ops cost — but fights the ecosystem gravity for a trading-research product and the user's team direction.

### B) Python-only (FastAPI + server-rendered UI, e.g. Jinja/HTMX/Streamlit)
- Pros: one language, strongest quant libs.
- Cons: research UI in the brief (equity overlays, paginated trades, diff views, SSE progress, template gallery) is materially harder to build well without React; Streamlit state/execution model actively fights reproducibility guarantees (rerun semantics, hidden global state). Rejected for UX reasons, not language reasons.

### C) Polyglot: Python FastAPI backend + React (Vite) SPA frontend  ← CHOSEN
- Backend (Python 3.12): deterministic core (`alphalab_core`: strategy schema, indicators with numpy, engine, metrics), FastAPI API layer, asyncio in-process job queue, SQLAlchemy 2 + SQLite persistence, AI orchestration (`gemini` + rule-based fallback).
- Frontend (TypeScript, React 18 + Vite + TanStack Query): pure rendering, Zod-validated forms generated from the shared JSON Schema, no authoritative math.
- Contract bridge: **one canonical `StrategySpec` JSON Schema + OpenAPI** as source of truth. Pydantic v2 models generated/derived from it on the backend; Zod schemas generated from the same file on the frontend (`npm run codegen`). Contract tests assert equivalence on every CI run.
- Node.js role in MVP: build-time and validation-mirror only (Vite toolchain, Zod form validation from the shared schema). **No separate Node backend service** — a third runtime would add deployment, logging, and failure modes with zero product benefit at this scale. Node re-enters only if a future BFF/SSR need is proven (see §Next.js below).

### D) Polyglot with Next.js instead of Vite SPA
- Considered because the user named it. Next.js earns its keep with SEO, server components, and edge SSR. AlphaLab is an authenticated-localhost research dashboard: no SEO, no public pages, no edge. Next.js adds a Node server process, SSR state pitfalls, and a second backend-adjacent layer that would tempt financial logic into server components — exactly the boundary violation the architecture exists to prevent.
- Decision: **Vite SPA for MVP** (static files served by FastAPI or `vite dev` proxy in development). Migration path to Next.js preserved: the frontend talks only to versioned REST, so a Next app can replace Vite later without backend changes. This is documented, not just claimed — no backend code imports frontend concepts.

### E) Polyglot with separate Node microservice (BFF/validation service)
- Rejected for MVP: introduces network hops into the validation path, doubles health-checking, and creates the "which service validated this?" audit ambiguity. Single Python API process keeps the audit trail linear.

## Decision
**C.** Python 3.12 + FastAPI (Pydantic v2, SQLAlchemy 2, `aiosqlite`, `pytest` + `hypothesis`) for everything behind `/api`; TypeScript React + Vite (Zod, TanStack Query, uPlot/ECharts) for `apps/web`; shared JSON Schema + OpenAPI contract with codegen + equivalence tests; Node confined to frontend toolchain + validation mirror.

Repo shape:
```text
backend/                 # Python: alphalab_core (pure) + alphalab_api (FastAPI) + alphalab_ai + alphalab_store
  alphalab_core/         # strategy, indicators, engine, metrics — pure: no fastapi/sqlalchemy/httpx imports
  alphalab_api/          # routes, jobs (asyncio), orchestration
  alphalab_store/        # sqlalchemy models, migrations (alembic), repos
  alphalab_ai/           # AIAssistant port, rule-based provider, gemini provider
  tests/                 # pytest: fixtures, golden vectors, hypothesis properties
web/                     # TypeScript React+Vite app (Zod schemas generated from shared/schemas/strategy.spec.json)
shared/schemas/          # canonical JSON Schema + OpenAPI — THE contract both sides codegen from
data/samples/
```

Dependency rule (enforced by tests, not just convention): `alphalab_core` imports stdlib + numpy only. `alphalab_api` orchestrates. `web/` never computes money. A CI "purity test" fails the build on banned imports (`fastapi`, `sqlalchemy`, `httpx`, `google.generativeai`) inside `alphalab_core`, and on engine/math keywords inside `web/src` outside `formatters/`.

## Scenarios walked before deciding
1. **Lookahead regression in numpy code** — vectorized shifts (`close.shift(-1)`) are the classic leak. Mitigation chosen: engine iterates bars in Python order with explicit index loop (not vectorized signal generation); numpy used only *inside* single-indicator kernels with causal windows; the `offsetBars ≥ 0` + future-mutation property tests (ported to hypothesis) guard both implementations.
2. **Schema drift (Pydantic vs Zod)** — the failure mode that kills polyglots. Mitigation: single `strategy.spec.json` + codegen + CI equivalence test (every example valid in one must validate in the other; every reject-case must reject in both). Drift becomes a red build, not a production mystery.
3. **Two-toolchain fatigue** — mitigated by pinning (`uv.lock` + `package-lock.json`), one `make` surface (`make dev/test/typecheck`), and keeping Python as the only runtime with business logic.
4. **Scale-up later** — engine stays process-local and pure, so a future worker pool (arq/dramatiq or separate container) can import `alphalab_core` unchanged. No rewrite needed; see ADR 0007.

## Consequences
+ Ecosystem fit (numpy/pytest/hypothesis, Python AI SDKs), team-direction fit, honest localhost ops (one API process + static SPA).
− Two toolchains, codegen discipline required, contributor must read Python *and* TS. Accepted: the contract-test gate makes the cost visible and bounded.
− Contributors cannot "just" add a strategy field in one language — they must edit the shared schema first. This friction is intentional (it is the reproducibility guarantee).
