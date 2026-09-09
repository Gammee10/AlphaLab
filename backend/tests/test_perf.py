"""Performance smoke: bounded runtime + determinism at scale (docs/testing.md).

Generous bound (catches 10x regressions, not laptop variance). CI records the
duration; the gate is completion, not a strict number.
"""

from __future__ import annotations

import time
from decimal import Decimal

from alphalab_core.config import BacktestConfig, Costs
from alphalab_core.engine import run_backtest
from alphalab_marketdata import to_bar_arrays
from alphalab_marketdata.synthetic import generate_synthetic


def _spec() -> dict:
    return {
        "specVersion": "1.0",
        "universe": {"symbol": "BTCUSD", "timeframe": "H1"},
        "indicators": [
            {"id": "ema50", "kind": "EMA", "period": 50},
            {"id": "ema200", "kind": "EMA", "period": 200},
            {"id": "atr", "kind": "ATR", "period": 14},
        ],
        "entry": {"direction": "long", "logic": "all", "conditions": [
            {"id": "c1", "left": {"kind": "indicator", "ref": "ema50"},
             "op": ">", "right": {"kind": "indicator", "ref": "ema200"}}]},
        "exits": {"stopLoss": {"kind": "atr", "atrMultiplier": 1.5},
                  "takeProfit": {"kind": "rr", "ratio": 2},
                  "trailing": {"kind": "none"}, "timeStop": {"kind": "none"},
                  "oppositeSignalExit": False},
        "filters": {},
        "risk": {"riskPerTradePct": 0.5, "maxNotionalMult": 3, "leverageMax": 10},
        "execution": {"fillBasis": "next_open"},
    }


def test_100k_bars_bounded_and_deterministic() -> None:
    rows = generate_synthetic("BTCUSD", "H1", "2020-01-01T00:00:00Z", 100_000, 7,
                              40000.0, volatility=150.0, pip_size=1.0, with_volume=True)
    bars = to_bar_arrays(rows)
    cfg = BacktestConfig(symbol="BTCUSD", bar_step_ms=3_600_000, start_ms=rows[0].open_time,
                         end_ms=rows[-1].open_time, initial_capital=Decimal("10000"), costs=Costs())
    started = time.perf_counter()
    first = run_backtest(_spec(), bars, cfg)
    elapsed = time.perf_counter() - started
    print(f"\n100k-bar run: {elapsed:.1f}s, trades={len(first.trades)}")
    assert elapsed < 30.0
    second = run_backtest(_spec(), bars, cfg)
    assert [(t.entry_bar, t.exit_bar, t.net_pnl) for t in first.trades] == [
        (t.entry_bar, t.exit_bar, t.net_pnl) for t in second.trades]
