"""Versioned instrument metadata (docs/domain-model.md).

Sizing math depends on lot steps and pip sizes, so the metadata version is part
of every run's identity hash. Changing a step creates a new meta version; old
runs keep theirs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

INSTRUMENT_META_VERSION = "instruments/1.0"


@dataclass(frozen=True)
class InstrumentMeta:
    symbol: str
    pip_size: Decimal
    lot_step: Decimal
    min_qty: Decimal
    price_decimals: int


_INSTRUMENTS: dict[str, InstrumentMeta] = {
    "EURUSD": InstrumentMeta("EURUSD", Decimal("0.0001"), Decimal("1000"), Decimal("1000"), 5),
    "GBPUSD": InstrumentMeta("GBPUSD", Decimal("0.0001"), Decimal("1000"), Decimal("1000"), 5),
    "XAUUSD": InstrumentMeta("XAUUSD", Decimal("0.1"), Decimal("1"), Decimal("1"), 2),
    "BTCUSD": InstrumentMeta("BTCUSD", Decimal("1"), Decimal("0.001"), Decimal("0.001"), 2),
}


def get_instrument(symbol: str) -> InstrumentMeta:
    try:
        return _INSTRUMENTS[symbol]
    except KeyError:
        raise ValueError(f"unknown instrument: {symbol!r}") from None
