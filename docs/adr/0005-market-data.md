# ADR 0005 — Market-data scope: 4 symbols, independent TFs, no live providers in MVP

## Context
Brief lists broad markets/timeframes/providers. Each axis multiplies validation, licensing, and resampling risk.

## Decision
MVP: `EURUSD, GBPUSD, XAUUSD, BTCUSD` × `M5–D1` as **independent datasets** (no resampling); sources: CSV import + bundled samples + seeded synthetic. `MarketDataProvider` port defined; live adapters (Binance/Dukascopy/OANDA) deferred. No equities (corporate actions deferred with them).

## Consequences
+ Small, licensable, testable surface; timeframe comparison stays honest (separate runs, labeled).
− No auto multi-TF confirmation strategies; users asking get `NOT_SUPPORTED_IN_MVP` + roadmap pointer. Acceptable: prevents a resampling-lookahead bug class in v1.
