"""Canonical bar arrays shared by indicators and engine.

All computation is causal: kernel output at index ``t`` may only depend on
bars ``0..t``. Every indicator returns NaN for warming-up bars; the engine
suppresses signals while any *referenced* indicator is warming up.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BarArrays:
    open_time: np.ndarray  # int64 UTC ms, ascending
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return int(self.open_time.shape[0])


def bars_from_lists(
    open_time: list[int],
    o: list[float],
    h: list[float],
    l: list[float],
    c: list[float],
    v: list[float] | None = None,
) -> BarArrays:
    n = len(c)
    return BarArrays(
        open_time=np.array(open_time, dtype=np.int64),
        open=np.array(o, dtype=np.float64),
        high=np.array(h, dtype=np.float64),
        low=np.array(l, dtype=np.float64),
        close=np.array(c, dtype=np.float64),
        volume=np.array(v if v is not None else [0.0] * n, dtype=np.float64),
    )


@dataclass(frozen=True)
class IndicatorResult:
    """One named output per key, e.g. BB -> {upper, middle, lower}."""

    values: dict[str, np.ndarray]
    warmup: int  # bars [0, warmup) are warming up; values there are NaN

    def is_warm(self, t: int) -> bool:
        return t >= self.warmup
