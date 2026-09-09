"""Backtest configuration and run records (docs/domain-model.md, backtest-engine.md).

Money uses Decimal throughout. Prices arrive as floats from bar arrays and are
converted once via ``Decimal(str(x))`` -- never ``Decimal(float)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ENGINE_VERSION = "engine/1.0"

EPS = Decimal("0.000000001")


def money(value: float | int | str | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class Costs:
    spread_bps: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    commission_per_unit: Decimal = Decimal("0")


@dataclass(frozen=True)
class BacktestConfig:
    symbol: str
    bar_step_ms: int
    start_ms: int
    end_ms: int
    initial_capital: Decimal
    costs: Costs = field(default_factory=Costs)


@dataclass
class Order:
    signal_bar: int
    signal_time: int
    direction: str
    state: str  # filled | skipped_capital | skipped_min_qty | skipped_min_stop | ignored_pyramid | expired_end_of_data
    fill_bar: int | None = None
    fill_time: int | None = None
    qty: Decimal = Decimal("0")
    fill_price: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")


@dataclass
class Trade:
    entry_bar: int
    entry_time: int
    exit_bar: int
    exit_time: int
    direction: str  # long | short
    qty: Decimal
    entry_price: Decimal
    exit_price: Decimal
    fees: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    intended_risk: Decimal
    realized_risk: Decimal
    exit_reason: str  # stop | target | trailing | time | opposite | end-of-data
    ambiguous: bool = False


@dataclass
class RunPayload:
    trades: list[Trade]
    orders: list[Order]
    equity: list[tuple[int, Decimal]]  # (open_time, equity) per in-range bar close
    warnings: dict[str, int | bool]
    assumptions: list[str]
    engine_version: str = ENGINE_VERSION
