# ADR 0011 — Reproducibility hardening: warmup lookback, instrument metadata, hash scope

## Context
Adversarial review found three identity gaps that could fork supposedly identical runs: (1) indicators seeded at `startTime` with no pre-history (cold-start mis-seeding); (2) lot steps/pip sizes affecting sizing but unversioned and unhashed; (3) ambiguous hash scope (metrics versioning, sliced-vs-full dataset hash).

## Decision
- **Warmup lookback rule:** API supplies bars over `[startTime − lookbackWindow, endTime]` with `warmupBars = max(3×maxPeriod, 50)`; computation covers the lookback, signals/fills only in-range; deficit flagged `coldStart` with count. Cold-start equivalence test required.
- **Versioned instrument metadata** (`instrument_meta`, `instruments/1.0` MVP values) included in every run hash; changes create new meta versions, never mutate.
- **Exact hash scope:** `configHash` ⊇ period/capital/costs/instrumentMetaVersion/sample labels; `datasetHash` = full-dataset `barsHash`; `resultHash = sha256(specHash + datasetHash + configHash + engineVersion + instrumentMetaVersion + canonicalTrades)`; `engineVersion` covers execution AND metrics.
- Money persisted as TEXT/`Decimal`; market bars stay REAL.

## Consequences
+ "Same inputs → same bytes" now includes the inputs that were previously implicit; six-months-later reproduction is provable from the run row alone.
− Warmup fetch adds I/O per run (bounded, indexed range read) and a `coldStart` UX state implementers must render, not hide.
