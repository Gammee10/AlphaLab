"""Indicator correctness: hand-computed values (exact), golden regression vectors."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alphalab_core.bars import bars_from_lists
from alphalab_core.indicators import (
    adx,
    atr,
    bollinger,
    compute_all,
    compute_indicator,
    donchian,
    ema,
    macd,
    rsi,
    sma,
    vwap,
)

T = [1_700_000_000_000 + i * 60_000 for i in range(7)]


def test_sma_hand_computed() -> None:
    bars = bars_from_lists(T[:5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    r = sma(bars, 3)
    assert r.warmup == 2
    got = r.values["value"]
    assert np.isnan(got[0]) and np.isnan(got[1])
    assert list(got[2:]) == [2.0, 3.0, 4.0]


def test_ema_hand_computed() -> None:
    # k = 2/4 = 0.5, seeded from first close 1.0.
    bars = bars_from_lists(T[:5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    r = ema(bars, 3)
    assert r.warmup == 2
    assert list(r.values["value"]) == [1.0, 1.5, 2.25, 3.125, 4.0625]


def test_rsi_hand_computed_wilder() -> None:
    closes = [10, 11, 12, 13, 12, 11, 10]
    bars = bars_from_lists(T, closes, closes, closes, closes)
    r = rsi(bars, 3)
    assert r.warmup == 3
    got = r.values["value"]
    assert all(np.isnan(got[:3]))
    assert got[3] == pytest.approx(100.0)
    assert got[4] == pytest.approx(66.6666667)
    assert got[5] == pytest.approx(44.4444444)
    assert got[6] == pytest.approx(29.6296296)


def test_rsi_flat_is_50_not_nan() -> None:
    closes = [10] * 6
    bars = bars_from_lists(T[:6], closes, closes, closes, closes)
    got = rsi(bars, 3).values["value"]
    assert got[3] == 50.0 and got[5] == 50.0


def test_atr_hand_computed() -> None:
    o = [10, 10, 11, 12]
    h = [11, 12, 13, 12.5]
    l = [9, 10, 11, 11]
    c = [10, 11, 12, 11.5]
    bars = bars_from_lists(T[:4], o, h, l, c)
    r = atr(bars, 3)
    assert r.warmup == 2
    got = r.values["value"]
    assert np.isnan(got[0]) and np.isnan(got[1])
    assert got[2] == pytest.approx(2.0)
    assert got[3] == pytest.approx(1.8333333)


def test_macd_line_and_warmup() -> None:
    closes = [10, 11, 12, 13, 14, 15, 16, 17]
    bars = bars_from_lists(T[:8] + [T[-1]], closes, closes, closes, closes)
    r = macd(bars, 2, 4, 2)
    assert r.warmup == (4 - 1) + (2 - 1) == 4
    # Hand-computed: EMA(2) k=2/3 -> e4=13.5061728; EMA(4) k=0.4 -> s4=12.6944.
    assert r.values["macd"][4] == pytest.approx(0.8117728, abs=1e-6)
    flat = bars_from_lists(T[:8] + [T[-1]], [5] * 8, [5] * 8, [5] * 8, [5] * 8)
    assert macd(flat, 2, 4, 2).values["macd"][7] == pytest.approx(0.0, abs=1e-12)


def test_bollinger_hand_computed() -> None:
    closes = [1, 2, 3, 4, 5]
    bars = bars_from_lists(T[:5], closes, closes, closes, closes)
    r = bollinger(bars, 3, 2.0)
    assert r.warmup == 2
    assert r.values["middle"][2] == pytest.approx(2.0)
    assert r.values["upper"][2] == pytest.approx(2.0 + 2 * 0.8164965809)
    assert r.values["lower"][2] == pytest.approx(2.0 - 2 * 0.8164965809)
    assert r.values["middle"][4] == pytest.approx(4.0)


def test_donchian_hand_computed() -> None:
    h = [11, 12, 13, 12.5]
    l = [9, 10, 11, 11]
    bars = bars_from_lists(T[:4], h, h, l, h)
    r = donchian(bars, 3)
    assert r.warmup == 2
    assert r.values["upper"][2] == 13.0 and r.values["lower"][2] == 9.0
    assert r.values["upper"][3] == 13.0 and r.values["lower"][3] == 10.0
    assert r.values["middle"][3] == 11.5


def test_adx_bounded_and_warmup() -> None:
    closes = [float(10 + i) for i in range(40)]
    bars = bars_from_lists(
        [1_700_000_000_000 + i * 60_000 for i in range(40)],
        closes,
        [c + 1 for c in closes],
        [c - 1 for c in closes],
        closes,
    )
    r = adx(bars, 14)
    assert r.warmup == 26
    valid = r.values["value"][26:]
    assert len(valid) == 14
    assert all(0.0 <= v <= 100.0 for v in valid)
    assert valid[-1] > 20.0  # strong uninterrupted trend


def test_vwap_session_reset_and_zero_volume() -> None:
    t = [1_700_000_000_000, 1_700_000_060_000, 1_700_000_120_000]
    bars = bars_from_lists(t, [10, 11, 12], [10, 11, 12], [10, 11, 12], [10, 11, 12], [5, 0, 5])
    got = vwap(bars).values["value"]
    assert got[0] == pytest.approx(10.0)
    assert got[1] == pytest.approx(10.0)
    assert got[2] == pytest.approx(11.0)
    flat = bars_from_lists(t, [10, 10, 10], [10, 10, 10], [10, 10, 10], [10, 10, 10])
    assert all(np.isnan(vwap(flat).values["value"]))


def test_compute_all_and_dispatch() -> None:
    bars = bars_from_lists(T[:5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    out = compute_all(bars, [{"id": "e", "kind": "EMA", "period": 3}])
    assert list(out["e"].values["value"]) == [1.0, 1.5, 2.25, 3.125, 4.0625]
    assert compute_indicator(bars, {"id": "s", "kind": "SMA", "period": 3}).values["value"][4] == 4.0
    with pytest.raises(ValueError, match="unknown indicator kind"):
        compute_indicator(bars, {"id": "x", "kind": "Supertrend", "period": 10})


def test_golden_vectors_regression() -> None:
    path = Path(__file__).parent / "fixtures" / "indicators" / "golden_60.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    bars = bars_from_lists(
        fixture["open_time"],
        fixture["open"],
        fixture["high"],
        fixture["low"],
        fixture["close"],
        fixture["volume"],
    )
    for entry in fixture["indicators"]:
        result = compute_indicator(bars, entry["definition"])
        assert result.warmup == entry["warmup"], entry["definition"]["id"]
        for key, expected in entry["values"].items():
            got = result.values[key]
            assert len(got) == len(expected)
            for i, (g, e) in enumerate(zip(got, expected)):
                if e is None:
                    assert g != g, (entry["definition"]["id"], key, i)
                else:
                    assert g == pytest.approx(e, abs=1e-12), (entry["definition"]["id"], key, i)
