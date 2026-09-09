"""Metrics against known trade lists (exact money, oracle-checked statistics)."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from alphalab_core.config import Trade
from alphalab_core.metrics import compute_metrics


def ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def trade(net: int, exit_day: int, exit_hour: int = 12, qty: int = 10) -> Trade:
    t = ms(datetime(2024, 1, exit_day, exit_hour))
    gross = Decimal(net)
    return Trade(
        entry_bar=0, entry_time=t - 900_000, exit_bar=1, exit_time=t,
        signal_bar=0, signal_time=t - 1_800_000, direction="long", qty=Decimal(qty),
        entry_price=Decimal("100"), exit_price=Decimal("100") + gross / qty,
        fees=Decimal("0"), gross_pnl=gross, net_pnl=gross,
        intended_risk=Decimal("50"), realized_risk=Decimal("50"),
        exit_reason="target", ambiguous=False,
    )


def test_known_values() -> None:
    trades = [trade(100, 3), trade(-50, 4), trade(200, 10), trade(-100, 11)]
    equity = [(0, Decimal(x)) for x in (10000, 10100, 10050, 10250, 10150, 10150)]
    m = compute_metrics(trades, equity, Decimal("10000"), "H1")
    assert m["tradeCount"] == 4
    assert m["netProfit"] == Decimal("150")
    assert m["totalReturnPct"] == 1.5
    assert m["winRate"] == 0.5
    assert m["avgWin"] == Decimal("150")
    assert m["avgLoss"] == Decimal("-75")
    assert m["profitFactor"] == 2.0
    assert m["noLosses"] is False
    assert m["expectancy"] == Decimal("37.5")
    assert m["maxDrawdown"] == Decimal("100")
    assert m["maxDrawdownPct"] == 100 / 10250 * 100
    assert m["avgDrawdown"] == Decimal("50")
    assert m["maxWinStreak"] == 1 and m["maxLossStreak"] == 1
    assert m["sharpe"] is None and m["sharpeInsufficientData"] is True
    assert m["approxAnnualized"] is True
    assert [(b["period"], b["netPnl"], b["trades"]) for b in m["monthly"]] == [("2024-01", Decimal("150"), 4)]
    assert sum(b["trades"] for b in m["weekly"]) == 4
    assert len(m["deciles"]) == 9 and sum(m["histogram"]["bins"]) == 4
    assert {b["hour"] for b in m["byHour"]} == {11}  # signal 30 min before exit


def test_empty_and_no_losses() -> None:
    m = compute_metrics([], [(0, Decimal("10000"))], Decimal("10000"), "D1")
    assert m["tradeCount"] == 0 and m["netProfit"] == Decimal("0")
    assert m["winRate"] is None and m["profitFactor"] is None
    assert m["expectancy"] is None and m["avgDrawdown"] is None
    assert m["deciles"] == [] and m["histogram"]["bins"] == [0] * 10
    solo = [trade(50, 3)]
    m2 = compute_metrics(solo, [(0, Decimal("10000")), (1, Decimal("10050"))], Decimal("10000"), "D1")
    assert m2["profitFactor"] is None and m2["noLosses"] is True
    assert m2["avgLoss"] is None and m2["avgWin"] == Decimal("50")


def test_sharpe_oracle() -> None:
    trades = [trade(10 if i % 2 == 0 else -4, (i % 28) + 1) for i in range(30)]
    equity = [(i, Decimal("10000") + Decimal(i * 7 - (i % 5) * 13)) for i in range(120)]
    m = compute_metrics(trades, equity, Decimal("10000"), "H1")
    assert m["sharpe"] is not None and m["sharpeInsufficientData"] is False
    c0, prev, rets = 10000.0, 10000.0, []
    for _, e in equity:
        cur = float(e)
        rets.append((cur - prev) / prev)
        prev = cur
    expected = statistics.mean(rets) / statistics.stdev(rets) * (8760**0.5)
    assert m["sharpe"] == pytest.approx(expected, rel=1e-9)
