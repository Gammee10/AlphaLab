"""Deterministic synthetic OHLCV generator (docs/market-data.md).

Seeded ``random.Random`` GBM-ish walk. Used for tests, demos, and bundled
samples -- never for known-answer engine fixtures (those are hand-written).
Callers must pass a grid-aligned start time for the timeframe.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from . import TIMEFRAME_MS, BarRow


def generate_synthetic(
    symbol: str,
    timeframe: str,
    start_iso: str,
    bars: int,
    seed: int,
    start_price: float,
    volatility: float = 0.001,
    trend: float = 0.0,
    pip_size: float = 0.0001,
    with_volume: bool = False,
) -> list[BarRow]:
    if timeframe not in TIMEFRAME_MS:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    step = TIMEFRAME_MS[timeframe]
    dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    t0 = int(dt.astimezone(timezone.utc).timestamp() * 1000)
    rng = random.Random(seed)
    out: list[BarRow] = []
    price = start_price
    for i in range(bars):
        drift = rng.uniform(-volatility, volatility) + trend
        o = price
        c = max(o + drift, pip_size)
        h = max(o, c) + rng.uniform(0, volatility / 2)
        low = min(o, c) - rng.uniform(0, volatility / 2)
        low = max(low, pip_size)
        v = rng.uniform(500, 2000) if with_volume else 0.0
        out.append(BarRow(t0 + i * step, o, h, low, c, v))
        price = c
    return out


def rows_to_csv(rows: list[BarRow]) -> str:
    lines = ["open_time,open,high,low,close,volume"]
    for r in rows:
        ts = datetime.fromtimestamp(r.open_time / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        lines.append(f"{ts},{r.open},{r.high},{r.low},{r.close},{r.volume}")
    return "\n".join(lines) + "\n"
