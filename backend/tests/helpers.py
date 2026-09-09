"""Shared engine-test fixtures: data builders with hand-known behavior."""

from __future__ import annotations

from decimal import Decimal

from alphalab_core.bars import BarArrays, bars_from_lists
from alphalab_core.config import BacktestConfig

T0 = 1_700_000_000_000
M15 = 900_000


def times(n: int, step: int = M15, start: int = T0) -> list[int]:
    return [start + i * step for i in range(n)]


def base_spec(**overrides) -> dict:
    spec: dict = {
        "specVersion": "1.0",
        "universe": {"symbol": "BTCUSD", "timeframe": "M15"},
        "indicators": [{"id": "sma2", "kind": "SMA", "period": 2}],
        "entry": {
            "direction": "long",
            "logic": "all",
            "conditions": [
                {
                    "id": "c1",
                    "left": {"kind": "price", "field": "close"},
                    "op": ">",
                    "right": {"kind": "price", "field": "close", "offsetBars": 1},
                }
            ],
        },
        "exits": {
            "stopLoss": {"kind": "pips", "pips": 1},
            "takeProfit": {"kind": "rr", "ratio": 2},
            "trailing": {"kind": "none"},
            "timeStop": {"kind": "none"},
            "oppositeSignalExit": False,
        },
        "filters": {},
        "risk": {"riskPerTradePct": 1, "maxNotionalMult": 5, "leverageMax": 10},
        "execution": {"fillBasis": "next_open"},
    }
    spec.update(overrides)
    return spec


def cfg(**overrides) -> BacktestConfig:
    args: dict = {"symbol": "BTCUSD", "bar_step_ms": M15, "start_ms": T0, "end_ms": T0 + 10 * M15,
                  "initial_capital": Decimal("10000")}
    args.update(overrides)
    return BacktestConfig(**args)


def basic_bars() -> BarArrays:
    # Signal at idx1 (101>100); fill open[2]=101; stop=100; target=103.
    return bars_from_lists(
        times(5),
        [100, 101, 101, 102, 103],
        [100, 101, 102, 103, 104],
        [100, 100, 100, 101, 102],
        [100, 101, 101, 102, 103],
    )
