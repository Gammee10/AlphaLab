"""Causal indicator kernels (docs/strategy-spec.md, indicator semantics).

Conventions (normative for engine tests):
- Every kernel iterates left-to-right; output[t] uses bars 0..t only.
- Warmup bars hold NaN and are counted in ``IndicatorResult.warmup``.
- EMA seeded from the first close; Wilder smoothing (RSI/ATR/ADX) seeded with
  the SMA of the first window; MACD signal seeded from the first line value.
- RSI with avg_loss == 0 and avg_gain == 0 is 50.0 (flat), 100.0 if only gains.
- VWAP resets at 00:00 UTC; zero cumulative volume yields NaN (engine treats as
  warming up; validation rejects VWAP on volume-less datasets outright).
- NaN inputs propagate to NaN outputs (never silently filled).
"""

from __future__ import annotations

from typing import cast

import numpy as np

from .bars import BarArrays, IndicatorResult

_NAN = float("nan")


def _ema_series(values: np.ndarray, period: int) -> np.ndarray:
    out = np.full(values.shape, _NAN)
    if values.size == 0:
        return out
    k = 2.0 / (period + 1)
    prev = values[0]
    out[0] = prev
    for i in range(1, values.size):
        v = values[i]
        prev = v * k + prev * (1.0 - k) if v == v else _NAN  # NaN propagates
        out[i] = prev
    return out


def sma(bars: BarArrays, period: int) -> IndicatorResult:
    out = np.full(bars.close.shape, _NAN)
    window_sum = 0.0
    for i in range(len(bars)):
        c = bars.close[i]
        window_sum += c
        if i >= period:
            window_sum -= bars.close[i - period]
        if i >= period - 1:
            out[i] = window_sum / period
    return IndicatorResult({"value": out}, period - 1)


def ema(bars: BarArrays, period: int) -> IndicatorResult:
    return IndicatorResult({"value": _ema_series(bars.close, period)}, period - 1)


def _wilder_smooth(seed: np.ndarray, period: int) -> np.ndarray:
    """Wilder smoothing of a per-bar series defined from index 0.

    First value at index ``period - 1`` = mean of seed[0..period-1].
    Correct for TR and directional movement (day-1 values are genuine:
    TR = H-L, DM = 0 with no prior bar). NOT correct for RSI deltas, which
    start at index 1 -- see ``rsi`` for dedicated seeding.
    """
    out = np.full(seed.shape, _NAN)
    if seed.size < period:
        return out
    avg = float(np.sum(seed[:period]))
    out[period - 1] = avg / period
    for i in range(period, seed.size):
        avg = avg - avg / period + seed[i]
        out[i] = avg / period
    return out


def _wilder_from_1(seed: np.ndarray, period: int) -> np.ndarray:
    """Wilder smoothing for delta-based series (RSI gains/losses).

    seed[0] is a placeholder; the first average covers seed[1..period] and
    lands at index ``period``.
    """
    out = np.full(seed.shape, _NAN)
    if seed.size <= period:
        return out
    avg = float(np.sum(seed[1 : period + 1]))
    out[period] = avg / period
    for i in range(period + 1, seed.size):
        avg = avg - avg / period + seed[i]
        out[i] = avg / period
    return out


def rsi(bars: BarArrays, period: int) -> IndicatorResult:
    n = len(bars)
    out = np.full(n, _NAN)
    if n == 0:
        return IndicatorResult({"value": out}, period)
    gains = np.zeros(n)
    losses = np.zeros(n)
    for i in range(1, n):
        d = bars.close[i] - bars.close[i - 1]
        if d > 0:
            gains[i] = d
        else:
            losses[i] = -d
    avg_gain = _wilder_from_1(gains, period)
    avg_loss = _wilder_from_1(losses, period)
    # First Wilder average covers deltas 1..period -> first RSI at index period.
    for i in range(period, n):
        ag, al = avg_gain[i], avg_loss[i]
        if al == 0.0:
            out[i] = 50.0 if ag == 0.0 else 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + ag / al)
    return IndicatorResult({"value": out}, period)


def atr(bars: BarArrays, period: int) -> IndicatorResult:
    n = len(bars)
    out = np.full(n, _NAN)
    if n == 0:
        return IndicatorResult({"value": out}, period - 1)
    tr = np.zeros(n)
    tr[0] = bars.high[0] - bars.low[0]
    for i in range(1, n):
        tr[i] = max(bars.high[i] - bars.low[i], abs(bars.high[i] - bars.close[i - 1]), abs(bars.low[i] - bars.close[i - 1]))
    smoothed = _wilder_smooth(tr, period)
    for i in range(period - 1, n):
        out[i] = smoothed[i]
    return IndicatorResult({"value": out}, period - 1)


def macd(bars: BarArrays, fast: int, slow: int, signal: int) -> IndicatorResult:
    fast_e = _ema_series(bars.close, fast)
    slow_e = _ema_series(bars.close, slow)
    line = fast_e - slow_e
    sig = _ema_series(line, signal)
    hist = line - sig
    return IndicatorResult(
        {"macd": line, "signal": sig, "histogram": hist}, (slow - 1) + (signal - 1)
    )


def bollinger(bars: BarArrays, period: int, std_dev: float) -> IndicatorResult:
    n = len(bars)
    upper = np.full(n, _NAN)
    middle = np.full(n, _NAN)
    lower = np.full(n, _NAN)
    for i in range(period - 1, n):
        window = bars.close[i - period + 1 : i + 1]
        mean = float(np.mean(window))
        sd = float(np.std(window))  # population std, per spec
        middle[i] = mean
        upper[i] = mean + std_dev * sd
        lower[i] = mean - std_dev * sd
    return IndicatorResult({"upper": upper, "middle": middle, "lower": lower}, period - 1)


def adx(bars: BarArrays, period: int) -> IndicatorResult:
    n = len(bars)
    out = np.full(n, _NAN)
    if n == 0:
        return IndicatorResult({"value": out}, 2 * period - 2)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr = np.zeros(n)
    tr[0] = bars.high[0] - bars.low[0]
    for i in range(1, n):
        up = bars.high[i] - bars.high[i - 1]
        down = bars.low[i - 1] - bars.low[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
        tr[i] = max(bars.high[i] - bars.low[i], abs(bars.high[i] - bars.close[i - 1]), abs(bars.low[i] - bars.close[i - 1]))
    s_plus = _wilder_smooth(plus_dm, period)
    s_minus = _wilder_smooth(minus_dm, period)
    s_tr = _wilder_smooth(tr, period)
    dx = np.full(n, _NAN)
    for i in range(period - 1, n):
        denom = s_plus[i] + s_minus[i]
        dx[i] = 0.0 if denom == 0.0 else 100.0 * abs(s_plus[i] - s_minus[i]) / s_tr[i] if s_tr[i] != 0.0 else 0.0
    # First ADX = SMA of first `period` DX values (indices period-1 .. 2*period-2).
    first = 2 * period - 2
    if n > first:
        out[first] = float(np.nanmean(dx[period - 1 : first + 1]))
        for i in range(first + 1, n):
            if dx[i] == dx[i]:  # not NaN
                out[i] = (out[i - 1] * (period - 1) + dx[i]) / period
            else:
                out[i] = out[i - 1]
    return IndicatorResult({"value": out}, 2 * period - 2)


def donchian(bars: BarArrays, period: int) -> IndicatorResult:
    n = len(bars)
    upper = np.full(n, _NAN)
    lower = np.full(n, _NAN)
    for i in range(period - 1, n):
        upper[i] = float(np.max(bars.high[i - period + 1 : i + 1]))
        lower[i] = float(np.min(bars.low[i - period + 1 : i + 1]))
    mid = (upper + lower) / 2.0
    return IndicatorResult({"upper": upper, "lower": lower, "middle": mid}, period - 1)


def vwap(bars: BarArrays) -> IndicatorResult:
    n = len(bars)
    out = np.full(n, _NAN)
    cum_pv = 0.0
    cum_v = 0.0
    day_ms = 86_400_000
    current_day = None
    for i in range(n):
        day = int(bars.open_time[i] // day_ms)
        if day != current_day:
            current_day = day
            cum_pv = 0.0
            cum_v = 0.0
        typical = (bars.high[i] + bars.low[i] + bars.close[i]) / 3.0
        cum_pv += typical * bars.volume[i]
        cum_v += bars.volume[i]
        if cum_v > 0.0:
            out[i] = cum_pv / cum_v
    return IndicatorResult({"value": out}, 0)


_PERIOD_KERNELS = {"SMA": sma, "EMA": ema, "RSI": rsi, "ATR": atr, "ADX": adx, "Donchian": donchian}


def _dispatch(bars: BarArrays, definition: dict[str, object]) -> IndicatorResult:
    kind = definition["kind"]
    if kind in ("SMA", "EMA", "RSI", "ATR", "ADX", "Donchian"):
        return _PERIOD_KERNELS[str(kind)](bars, cast(int, definition["period"]))
    if kind == "MACD":
        return macd(
            bars,
            cast(int, definition["fast"]),
            cast(int, definition["slow"]),
            cast(int, definition["signal"]),
        )
    if kind == "BB":
        return bollinger(bars, cast(int, definition["period"]), cast(float, definition["stdDev"]))
    if kind == "VWAP":
        return vwap(bars)
    raise ValueError(f"unknown indicator kind: {kind!r}")


def compute_indicator(bars: BarArrays, definition: dict[str, object]) -> IndicatorResult:
    return _dispatch(bars, definition)


def compute_all(bars: BarArrays, definitions: list[dict[str, object]]) -> dict[str, IndicatorResult]:
    return {str(d["id"]): compute_indicator(bars, d) for d in definitions}
