# ADR 0007 — In-process job queue + process-pool engine, no Redis

## Context
Backtests range from instant to multi-second; UI must stay responsive with progress/cancel. Second review found the original wording let the CPU-bound engine run on the event loop (would freeze SSE/API) and left the idempotency race undefined.

## Decision
In-process asyncio queue for orchestration; engine execution offloaded — sync path (`< 200k` bars) in FastAPI's threadpool, async path (`≥ 200k`) in `ProcessPoolExecutor(max_workers=2)` (import-safe `alphalab_core`, plain-data handoff, DB-polled cancel flags, process-kill timeout). Idempotent dedupe resolved via `UNIQUE(result_hash)` catch-and-return-existing. Concurrency 2, queue 20, 120s timeout, sweep ≤ 32. No Redis/Celery/arq in MVP (arq remains the named successor).

## Consequences
+ Event loop never blocked; two jobs truly parallel; determinism structural (pure function, no shared state); zero infra.
− Spawn/pickle constraints on core (import-safety required and tested); restart drops queued items (accepted, documented); process startup cost per run (~100ms, negligible vs run time).
