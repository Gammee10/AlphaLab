"""Authoritative performance metrics (docs/results-experiments.md, normative).

Formulas implemented exactly as documented. Money aggregates are Decimal;
statistical ratios are float. Null (None) marks inapplicable, never 0:
N=0 win rate, empty win/loss sides, no-loss profit factor, under-sampled Sharpe.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .config import Trade

PERIODS_PER_YEAR = {"M5": 105120, "M15": 35040, "H1": 8760, "H4": 2190, "D1": 365}


def _d(x: Decimal | int) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(x)


def compute_metrics(
    trades: list[Trade],
    equity: list[tuple[int, Decimal]],
    initial_capital: Decimal | int | float,
    timeframe: str,
) -> dict[str, Any]:
    c0 = _d(Decimal(str(initial_capital)))
    nets = [t.net_pnl for t in trades]
    n = len(nets)
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gross_profit = sum(wins, Decimal("0"))
    gross_loss = sum(losses, Decimal("0"))
    net_profit = sum(nets, Decimal("0"))

    metrics: dict[str, Any] = {
        "tradeCount": n,
        "netProfit": net_profit,
        "totalReturnPct": float(net_profit / c0 * 100) if c0 != 0 else None,
        "winRate": (len(wins) / n) if n else None,
        "avgWin": (gross_profit / len(wins)) if wins else None,
        "avgLoss": (gross_loss / len(losses)) if losses else None,
        "profitFactor": (float(gross_profit / abs(gross_loss))) if gross_loss != 0 else None,
        "noLosses": n > 0 and not losses,
        "expectancy": (net_profit / n) if n else None,
    }

    # Drawdown over full-resolution equity.
    peak = c0
    max_dd = Decimal("0")
    max_dd_pct = 0.0
    episodes: list[Decimal] = []
    cur_trough = c0
    in_dd = False
    for _, e in equity:
        e = _d(e)
        if e > peak:
            if in_dd:
                episodes.append(peak - cur_trough)
                in_dd = False
            peak = e
            cur_trough = e
        elif e < peak:
            if not in_dd:
                in_dd = True
                cur_trough = e
            elif e < cur_trough:
                cur_trough = e
            dd = peak - e
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = float(dd / peak * 100) if peak != 0 else 0.0
    metrics["maxDrawdown"] = max_dd
    metrics["maxDrawdownPct"] = max_dd_pct
    metrics["avgDrawdown"] = (sum(episodes, Decimal("0")) / len(episodes)) if episodes else None

    # Streaks in exit order.
    max_w = max_l = cur_w = cur_l = 0
    for x in nets:
        if x > 0:
            cur_w += 1
            cur_l = 0
        elif x < 0:
            cur_l += 1
            cur_w = 0
        else:
            cur_w = cur_l = 0
        max_w = max(max_w, cur_w)
        max_l = max(max_l, cur_l)
    metrics["maxWinStreak"] = max_w
    metrics["maxLossStreak"] = max_l

    # Sharpe on per-bar equity returns; riskFree = 0; strict guards.
    sharpe: float | None = None
    if n >= 30 and len(equity) >= 101:
        rets: list[float] = []
        prev = float(c0)
        for _, e in equity:
            cur = float(_d(e))
            rets.append((cur - prev) / prev if prev != 0 else 0.0)
            prev = cur
        if len(rets) > 1:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            sd = math.sqrt(var)
            if sd > 0:
                sharpe = mean / sd * math.sqrt(PERIODS_PER_YEAR[timeframe])
    metrics["sharpe"] = sharpe
    metrics["sharpeInsufficientData"] = sharpe is None
    metrics["approxAnnualized"] = True

    # Periodic buckets (UTC month + ISO week).
    monthly: dict[str, dict[str, Any]] = {}
    weekly: dict[str, dict[str, Any]] = {}
    for t in trades:
        dt = datetime.fromtimestamp(t.exit_time / 1000, tz=timezone.utc)
        for key, store in (
            (dt.strftime("%Y-%m"), monthly),
            (f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}", weekly),
        ):
            b = store.setdefault(key, {"netPnl": Decimal("0"), "trades": 0, "wins": 0})
            b["netPnl"] += t.net_pnl
            b["trades"] += 1
            if t.net_pnl > 0:
                b["wins"] += 1
    metrics["monthly"] = [
        {"period": k, "netPnl": v["netPnl"], "trades": v["trades"],
         "winRate": v["wins"] / v["trades"] if v["trades"] else None}
        for k, v in sorted(monthly.items())
    ]
    metrics["weekly"] = [
        {"period": k, "netPnl": v["netPnl"], "trades": v["trades"],
         "winRate": v["wins"] / v["trades"] if v["trades"] else None}
        for k, v in sorted(weekly.items())
    ]

    # By-session: hourly buckets of signal-bar hour (MVP-lite).
    hours: dict[int, dict[str, Any]] = {}
    for t in trades:
        h = datetime.fromtimestamp(t.signal_time / 1000, tz=timezone.utc).hour
        b = hours.setdefault(h, {"netPnl": Decimal("0"), "trades": 0})
        b["netPnl"] += t.net_pnl
        b["trades"] += 1
    metrics["byHour"] = [
        {"hour": h, "netPnl": hours[h]["netPnl"], "trades": hours[h]["trades"]} for h in sorted(hours)
    ]

    # Distribution: deciles + 10-bin histogram over net P&L (float for binning).
    if nets:
        ordered: list[float] = sorted(float(x) for x in nets)
        metrics["deciles"] = [ordered[min(int(q * n), n - 1)] for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
        lo: float = ordered[0]
        hi: float = ordered[-1]
        width = (hi - lo) / 10 if hi > lo else 1.0
        bins = [0] * 10
        for val in ordered:
            idx = min(int((val - lo) / width), 9) if width > 0 else 0
            bins[idx] += 1
        metrics["histogram"] = {"lo": lo, "hi": hi, "bins": bins}
    else:
        metrics["deciles"] = []
        metrics["histogram"] = {"lo": 0.0, "hi": 0.0, "bins": [0] * 10}
    return metrics
