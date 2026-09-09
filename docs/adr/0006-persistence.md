# ADR 0006 — SQLite single-file persistence, immutable history, content hashing

## Context
Need reproducible audit trail (strategy/dataset/run identity) with zero-ops localhost deployment.

## Options
A) Postgres. B) SQLite single file + triggers. C) Files-only JSON store.

## Decision
**B** (SQLite WAL via SQLAlchemy 2 + Alembic, hand-authored DDL). `strategy_versions`, `datasets`, `backtest_runs` immutable via triggers + repo guards; identity by `sha256` canonical hashes; `resultHash` covers spec+data+config+engine version. Schema: `docs/persistence.md`.

## Consequences
+ Reproducibility by construction; backup = copy file; sufficient to ~2M bars.
− Concurrency ceiling (fine for 2-worker in-process queue); multi-user/cloud later needs Postgres migration — mitigated by `user_id` reservation and repo-layer isolation.
