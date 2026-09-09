"""One-shot generator for tests/fixtures/indicators/golden_60.json.

The committed file is a regression net (byte-stable expectations). It does NOT
prove formula correctness -- that comes from the hand-computed tests in
test_indicators.py. Run: python scripts/gen_indicator_fixtures.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from alphalab_core.bars import bars_from_lists  # noqa: E402
from alphalab_core.indicators import compute_indicator  # noqa: E402

DEFS = [
    {"id": "sma10", "kind": "SMA", "period": 10},
    {"id": "ema12", "kind": "EMA", "period": 12},
    {"id": "ema26", "kind": "EMA", "period": 26},
    {"id": "rsi14", "kind": "RSI", "period": 14},
    {"id": "atr14", "kind": "ATR", "period": 14},
    {"id": "macd", "kind": "MACD", "fast": 12, "slow": 26, "signal": 9},
    {"id": "bb20", "kind": "BB", "period": 20, "stdDev": 2.0},
    {"id": "adx14", "kind": "ADX", "period": 14},
    {"id": "don20", "kind": "Donchian", "period": 20},
    {"id": "vwap", "kind": "VWAP"},
]


def main() -> None:
    rng = random.Random(20260909)
    base = 1.12000
    o, h, l, c, v, t = [], [], [], [], [], []
    t0 = 1_700_000_000_000
    for i in range(60):
        drift = rng.uniform(-0.001, 0.0012)
        o.append(base)
        close = base + drift
        high = max(o[-1], close) + rng.uniform(0, 0.0008)
        low = min(o[-1], close) - rng.uniform(0, 0.0008)
        h.append(high)
        l.append(low)
        c.append(close)
        v.append(rng.uniform(500, 2000))
        # M5 grid timestamps.
        t.append(t0 + i * 300_000)
        base = close
    bars = bars_from_lists(t, o, h, l, c, v)
    out = {
        "open_time": t,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "indicators": [],
    }
    for d in DEFS:
        r = compute_indicator(bars, d)
        values = {}
        for key, arr in r.values.items():
            values[key] = [None if float(x) != float(x) else float(x) for x in arr]
        out["indicators"].append({"definition": d, "warmup": r.warmup, "values": values})
    dest = BACKEND / "tests" / "fixtures" / "indicators" / "golden_60.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
