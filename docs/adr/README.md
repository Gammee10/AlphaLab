# ADRs

Index of architecturally significant decisions. Each file: context → options → decision → consequences.

- `0001-system-shape.md` — modular monolith, no microservices
- `0002-strategy-representation.md` — declarative JSON spec
- `0003-no-code-execution.md` — never execute AI/user code
- `0004-execution-timing.md` — closed-bar signals, next-open fills, pessimistic stops
- `0005-market-data.md` — focused instruments, CSV+synthetic, no live providers in MVP
- `0006-persistence.md` — SQLite single-file, immutable rows, content hashing
- `0007-job-model.md` — in-process queue, sync/async threshold, no Redis
- `0008-mvp-ai.md` — free-tier Gemini BYOK primary, rule-based fallback
- `0009-tech-stack.md` — polyglot: Python FastAPI backend + TS React/Vite frontend (v2, supersedes TS-only)
- `0010-gemini-models.md` — Flash default, Pro opt-in for summaries
- `0011-reproducibility-hardening.md` — warmup lookback, instrument metadata, exact hash scope (adversarial-review fix)
