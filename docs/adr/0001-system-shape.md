# ADR 0001 — Modular monolith (polyglot: one Python process + static SPA), not microservices

## Context
Single-developer MVP, correctness-critical engine, localhost-first deployment. Brief warns against institutional infrastructure sprawl. Team direction favors Python for backend correctness/quant ecosystem.

## Options
A) Microservices (engine/data/api/ai separate deploys). B) Modular monolith + in-process jobs. C) Serverless functions.

## Decision
**B, polyglot instantiation:** one Python API process (FastAPI + pure `alphalab_core` + asyncio job queue + SQLite) serving a static React/Vite SPA. Module boundaries are language-appropriate (Python purity test for core; TS rendering-only rule for web) with a shared JSON-Schema/OpenAPI contract bridging them. See ADR 0009 for the language split rationale. Extraction seams (provider ports, pure core) preserved so a service split later is possible without rewrite.

## Consequences
+ Velocity, single test/type toolchain, trivial reproducibility, no network failure modes in the money path.
− No independent scaling of backtests; accepted (caps + queue cover MVP loads; shard path documented in `docs/persistence.md`).
