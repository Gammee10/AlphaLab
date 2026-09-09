# ADR 0004 — Execution timing: closed-bar signals, next-open fills, pessimistic stops

## Context
The realism-vs-complexity crux. OHLCV bars cannot resolve intrabar order; every choice here either leaks future data or invents precision.

## Options
A) Signal-bar-close fills (simplest, leaks: assumes tradability at a price only known at close). B) Next-open fills (realistic, standard). C) Tick-interpolated intrabar simulation (fake precision without ticks).

## Decision
**B + pessimistic intrabar rule**: signals on closed bar `t`, fills at open `t+1` with spread/slippage/commission; when a bar's range touches both stop and target, **stop first**; exact touches count as hits; entries skipped (never silently resized) on capital/qty violations. One position per run in `engine/1.0`. Full semantics: `docs/backtest-engine.md`.

## Consequences
+ No lookahead by construction; ambiguity disclosed (`ambiguousBars`, per-trade flag); tests are exact.
− Curves look worse than signal-close simulators; gap-through-stop behavior is harsh. This is the honest cost of bar-resolution backtesting and is documented per run in `assumptionsText`.
