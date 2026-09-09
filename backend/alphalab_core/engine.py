"""Deterministic backtest engine (docs/backtest-engine.md, normative).

Timing contract: signals on closed bar t, fills at open t+1, pessimistic
stop-first ambiguity, Decimal money, one position per run (engine/1.0).

NaN-suppression makes warmup structural: any unavailable operand value vetoes
the signal, so warming indicators can never generate trades.

Short-side signals use the mirrored condition tree (engine/1.0 semantics):
``>`` <-> ``<``, ``>=`` <-> ``<=``, crossesAbove <-> crossesBelow, ``==``/``!=``
unchanged. ``direction`` gates entries only; opposite-signal exits use the
evaluated opposite side. Tie-break when both sides fire on the same bar: long.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .bars import BarArrays, IndicatorResult
from .config import ENGINE_VERSION, BacktestConfig, Order, RunPayload, Trade, money
from .indicators import atr, compute_all
from .instruments import get_instrument

EPS = 1e-9
_MIRROR_OP = {
    ">": "<",
    "<": ">",
    ">=": "<=",
    "<=": ">=",
    "==": "==",
    "!=": "!=",
    "crossesAbove": "crossesBelow",
    "crossesBelow": "crossesAbove",
}


@dataclass
class _Position:
    direction: str
    qty: Decimal
    entry_price: Decimal
    entry_bar: int
    entry_time: int
    signal_bar: int
    signal_time: int
    entry_fees: Decimal
    stop: Decimal
    target: Decimal | None
    stop_distance: Decimal
    trail_mult: float | None
    trail_activation_r: float
    trail_level: Decimal | None
    time_bars: int | None


def mirror_tree(node: Any) -> Any:
    if "group" in node:
        return {
            "id": node["id"],
            "group": node["group"],
            "children": [mirror_tree(c) for c in node["children"]],
        }
    return {"id": node["id"], "left": node["left"], "op": _MIRROR_OP[node["op"]], "right": node["right"]}


class _Evaluator:
    def __init__(self, bars: BarArrays, values: dict[str, IndicatorResult]) -> None:
        self._bars = bars
        self._values = values

    def operand(self, op: dict[str, Any], t: int) -> float | None:
        kind = op["kind"]
        offset = int(op.get("offsetBars", 0))
        i = t - offset
        if i < 0:
            return None
        if kind == "const":
            return float(op["value"])
        if kind == "price":
            series = {
                "open": self._bars.open,
                "high": self._bars.high,
                "low": self._bars.low,
                "close": self._bars.close,
            }[op["field"]]
            return float(series[i])
        ref = self._values[op["ref"]]
        output = op.get("output") or next(iter(ref.values))
        v = float(ref.values[output][i])
        return v if v == v else None  # NaN (warming) vetoes

    def compare(
        self, op_name: str, a: float | None, b: float | None, t: int, left: Any, right: Any
    ) -> bool | None:
        """Three-valued compare: None means undecidable (missing data)."""
        if op_name in ("crossesAbove", "crossesBelow"):
            if t < 1:
                return None
            a_prev = self.operand(left, t - 1)
            b_prev = self.operand(right, t - 1)
            if a is None or b is None or a_prev is None or b_prev is None:
                return None
            if op_name == "crossesAbove":
                return bool(a_prev <= b_prev and a > b)
            return bool(a_prev >= b_prev and a < b)
        if a is None or b is None:
            return None
        if op_name == ">":
            return bool(a > b)
        if op_name == ">=":
            return bool(a >= b)
        if op_name == "<":
            return bool(a < b)
        if op_name == "<=":
            return bool(a <= b)
        if op_name == "==":
            return bool(abs(a - b) <= EPS)
        if op_name == "!=":
            return bool(abs(a - b) > EPS)
        raise ValueError(f"unknown op: {op_name!r}")

    def node(self, node: Any, t: int) -> bool | None:
        if "group" in node:
            results = [self.node(c, t) for c in node["children"]]
            if any(r is None for r in results):
                return None
            vals = [bool(r) for r in results]
            return all(vals) if node["group"] == "all" else any(vals)
        a = self.operand(node["left"], t)
        b = self.operand(node["right"], t)
        return self.compare(node["op"], a, b, t, node["left"], node["right"])


def _referenced_ids(tree: Any) -> set[str]:
    ids: set[str] = set()

    def visit(node: Any) -> None:
        if "group" in node:
            for child in node["children"]:
                visit(child)
        else:
            for side in ("left", "right"):
                op = node[side]
                if op["kind"] == "indicator":
                    ids.add(op["ref"])

    visit(tree)
    return ids


def _in_session(open_time_ms: int, start_h: int, end_h: int) -> bool:
    hour = (open_time_ms // 3_600_000) % 24
    if start_h <= end_h:
        return bool(start_h <= hour < end_h)
    return bool(hour >= start_h or hour < end_h)


def run_backtest(spec: dict[str, Any], bars: BarArrays, config: BacktestConfig) -> RunPayload:
    meta = get_instrument(config.symbol)
    n = len(bars)
    values = compute_all(bars, spec["indicators"])
    atr_id = next((d["id"] for d in spec["indicators"] if d["kind"] == "ATR"), None)
    filter_atr = atr(bars, 14)

    in_range = [i for i in range(n) if config.start_ms <= int(bars.open_time[i]) <= config.end_ms]
    in_set = set(in_range)

    entry_cfg = spec["entry"]
    direction = entry_cfg["direction"]
    top = {"id": "__top__", "group": entry_cfg["logic"], "children": entry_cfg["conditions"]}
    mirrored = {
        "id": "__top__",
        "group": entry_cfg["logic"],
        "children": [mirror_tree(c) for c in entry_cfg["conditions"]],
    }
    evaluator = _Evaluator(bars, values)

    exits = spec["exits"]
    filters = spec.get("filters") or {}
    session = filters.get("session") or {"kind": "none"}
    volatility = filters.get("volatility") or {"kind": "none"}
    spread_max = filters.get("spreadMaxBps")
    risk = spec["risk"]
    risk_pct = Decimal(str(risk["riskPerTradePct"]))
    max_notional_mult = Decimal(str(risk["maxNotionalMult"]))
    leverage_max = Decimal(str(risk["leverageMax"]))
    min_stop_raw = risk.get("minStopPriceDistance")
    min_stop_d = money(min_stop_raw) if min_stop_raw is not None else None

    costs = config.costs
    spread_frac = costs.spread_bps / Decimal("10000")
    slip_frac = costs.slippage_bps / Decimal("10000")

    trades: list[Trade] = []
    orders: list[Order] = []
    equity: list[tuple[int, Decimal]] = []
    warnings: dict[str, int | bool] = {
        "warmupBarsSkipped": 0,
        "capitalSkips": 0,
        "minQtySkips": 0,
        "minStopSkips": 0,
        "pyramidSkips": 0,
        "ambiguousBars": 0,
        "gapsEncountered": 0,
        "gapRiskExceeded": 0,
    }

    cash = money(config.initial_capital)
    position: _Position | None = None

    def spread_amt(price: Decimal) -> Decimal:
        return price * spread_frac / Decimal("2")

    def slip_amt(price: Decimal) -> Decimal:
        return price * slip_frac

    def exit_price_at_open(bar: int, side: str) -> Decimal:
        o = money(bars.open[bar])
        if side == "long":
            return o - spread_amt(o) - slip_amt(o)
        return o + spread_amt(o) + slip_amt(o)

    uses_exit_atr = any(
        isinstance(exits.get(slot), dict) and exits[slot].get("kind") == "atr"
        for slot in ("stopLoss", "takeProfit", "trailing")
    )

    def signal_and_filters(t: int, tree: Any, refs: set[str]) -> bool:
        """Full signal decision for bar t; counts warmup suppressions."""
        # Spec warmup rule: seeded indicators (EMA/MACD) are numeric from bar 0,
        # so NaN-suppression alone cannot cover them -- check warmup windows.
        if any(values[r].warmup > t for r in refs):
            warnings["warmupBarsSkipped"] = int(warnings["warmupBarsSkipped"]) + 1
            return False
        result = evaluator.node(tree, t)
        if result is None:
            warnings["warmupBarsSkipped"] = int(warnings["warmupBarsSkipped"]) + 1
            return False
        if not result:
            return False
        if session.get("kind") == "window":
            if not _in_session(
                int(bars.open_time[t]), session["startHourUtc"], session["endHourUtc"]
            ):
                return False
        if spread_max is not None and costs.spread_bps > money(spread_max):
            return False
        if volatility.get("kind") == "atr-range":
            v = float(filter_atr.values["value"][t])
            if v != v:
                warnings["warmupBarsSkipped"] = int(warnings["warmupBarsSkipped"]) + 1
                return False
            lo, hi = volatility.get("minAtr"), volatility.get("maxAtr")
            if lo is not None and v < float(lo):
                return False
            if hi is not None and v > float(hi):
                return False
        if uses_exit_atr and atr_id is not None:
            # Sizing/trailing ATR must be available at the signal bar; a price-only
            # signal with a warming ATR cannot be sized -- suppress, don't guess.
            av = float(values[atr_id].values["value"][t])
            if av != av:
                warnings["warmupBarsSkipped"] = int(warnings["warmupBarsSkipped"]) + 1
                return False
        return True

    # Each (signal bar, side) is evaluated at most once: the open phase reads
    # the same decision for opposite-close and entry handling. Without this,
    # warmup suppressions would be double-counted.
    _eval_cache: dict[tuple[int, str], bool] = {}
    _refs_cache = {"long": _referenced_ids(top), "short": _referenced_ids(mirrored)}

    def decided(t: int, side: str) -> bool:
        key = (t, side)
        if key not in _eval_cache:
            _eval_cache[key] = signal_and_filters(t, top if side == "long" else mirrored, _refs_cache[side])
        return _eval_cache[key]

    def exit_levels(t: int, side: str, entry_est: Decimal) -> tuple[Decimal, Decimal | None, Decimal] | None:
        """(stop, target_or_None, stop_distance) from signal-bar state; None if ATR missing."""
        atr_val: float | None = None
        if atr_id is not None:
            v = float(values[atr_id].values["value"][t])
            atr_val = v if v == v else None
        sl = exits["stopLoss"]
        if sl["kind"] == "atr":
            if atr_val is None:
                return None
            dist = money(atr_val) * money(sl["atrMultiplier"])
        else:
            dist = money(sl["pips"]) * meta.pip_size
        stop = entry_est - dist if side == "long" else entry_est + dist
        tp = exits["takeProfit"]
        target: Decimal | None
        if tp["kind"] == "none":
            target = None
        elif tp["kind"] == "rr":
            target = (
                entry_est + dist * money(tp["ratio"])
                if side == "long"
                else entry_est - dist * money(tp["ratio"])
            )
        else:
            if atr_val is None:
                return None
            tdist = money(atr_val) * money(tp["atrMultiplier"])
            target = entry_est + tdist if side == "long" else entry_est - tdist
        return stop, target, dist

    def close_position(bar: int, price: Decimal, reason: str, ambiguous: bool) -> None:
        nonlocal cash, position
        assert position is not None
        exit_comm = costs.commission_per_unit * position.qty
        if position.direction == "long":
            gross = (price - position.entry_price) * position.qty
        else:
            gross = (position.entry_price - price) * position.qty
        fees = position.entry_fees + exit_comm
        cash += gross - exit_comm
        intended = position.stop_distance * position.qty
        realized = abs(position.entry_price - position.stop) * position.qty
        trades.append(
            Trade(
                entry_bar=position.entry_bar,
                entry_time=position.entry_time,
                exit_bar=bar,
                exit_time=int(bars.open_time[bar]),
                signal_bar=position.signal_bar,
                signal_time=position.signal_time,
                direction=position.direction,
                qty=position.qty,
                entry_price=position.entry_price,
                exit_price=price,
                fees=fees,
                gross_pnl=gross,
                net_pnl=gross - fees,
                intended_risk=intended,
                realized_risk=realized,
                exit_reason=reason,
                ambiguous=ambiguous,
            )
        )
        position = None

    def open_position(bar: int, side: str, sig_bar: int) -> None:
        """Fill a pending entry at open[bar] from signal bar sig_bar. Requires flat."""
        nonlocal cash, position
        raw = money(bars.open[bar])
        if side == "long":
            fill = raw + spread_amt(raw) + slip_amt(raw)
        else:
            fill = raw - spread_amt(raw) - slip_amt(raw)
        est_close = money(bars.close[sig_bar])
        if side == "long":
            entry_est = est_close + spread_amt(est_close)
        else:
            entry_est = est_close - spread_amt(est_close)
        levels = exit_levels(sig_bar, side, entry_est)
        order = Order(signal_bar=sig_bar, signal_time=int(bars.open_time[sig_bar]), direction=side, state="filled")
        if levels is None:
            order.state = "skipped_capital"
            warnings["warmupBarsSkipped"] = int(warnings["warmupBarsSkipped"]) + 1
            orders.append(order)
            return
        stop, target, dist = levels
        if min_stop_d is not None and dist < min_stop_d:
            order.state = "skipped_min_stop"
            warnings["minStopSkips"] = int(warnings["minStopSkips"]) + 1
            orders.append(order)
            return
        equity_now = cash  # flat at fill time by construction
        risk_cash = equity_now * risk_pct / Decimal("100")
        qty_raw = risk_cash / dist if dist > 0 else Decimal("0")
        qty = (qty_raw // meta.lot_step) * meta.lot_step
        if qty < meta.min_qty:
            order.state = "skipped_min_qty"
            warnings["minQtySkips"] = int(warnings["minQtySkips"]) + 1
            orders.append(order)
            return
        if qty * entry_est > equity_now * max_notional_mult or qty * entry_est / leverage_max > cash:
            order.state = "skipped_capital"
            warnings["capitalSkips"] = int(warnings["capitalSkips"]) + 1
            orders.append(order)
            return
        entry_comm = costs.commission_per_unit * qty
        cash -= entry_comm
        trail_cfg = exits.get("trailing") or {"kind": "none"}
        time_cfg = exits.get("timeStop") or {"kind": "none"}
        position = _Position(
            direction=side,
            qty=qty,
            entry_price=fill,
            entry_bar=bar,
            entry_time=int(bars.open_time[bar]),
            signal_bar=sig_bar,
            signal_time=int(bars.open_time[sig_bar]),
            entry_fees=entry_comm,
            stop=stop,
            target=target,
            stop_distance=dist,
            trail_mult=float(trail_cfg["atrMultiplier"]) if trail_cfg.get("kind") == "atr" else None,
            trail_activation_r=float(trail_cfg.get("activationR", 1.0)) if trail_cfg.get("kind") == "atr" else 1.0,
            trail_level=None,
            time_bars=int(time_cfg["bars"]) if time_cfg.get("kind") == "bars" else None,
        )
        realized = abs(fill - stop) * qty
        if risk_cash > 0 and realized > risk_cash * Decimal("1.2"):
            warnings["gapRiskExceeded"] = int(warnings["gapRiskExceeded"]) + 1
        order.fill_bar = bar
        order.fill_time = int(bars.open_time[bar])
        order.qty = qty
        order.fill_price = fill
        order.fees = entry_comm
        orders.append(order)

    prev_time: int | None = None
    for idx_pos, i in enumerate(in_range):
        cur_time = int(bars.open_time[i])
        if prev_time is not None and config.bar_step_ms > 0:
            diff = cur_time - prev_time
            if diff > config.bar_step_ms:
                warnings["gapsEncountered"] = int(warnings["gapsEncountered"]) + int(diff // config.bar_step_ms - 1)
        prev_time = cur_time

        o = money(bars.open[i])
        h = money(bars.high[i])
        l = money(bars.low[i])
        c = money(bars.close[i])

        # --- open-phase: time-stop closes, opposite-signal closes, pending entries ---
        if position is not None and position.time_bars is not None and i >= position.entry_bar + position.time_bars:
            close_position(i, exit_price_at_open(i, position.direction), "time", False)
        if position is not None and exits.get("oppositeSignalExit") and (i - 1) in in_set:
            opp_side = "short" if position.direction == "long" else "long"
            if decided(i - 1, opp_side):
                close_position(i, exit_price_at_open(i, position.direction), "opposite", False)
        if (i - 1) in in_set:
            for side in ("long", "short"):
                if direction != "both" and direction != side:
                    continue
                if not decided(i - 1, side):
                    continue
                if position is not None and position.direction == side:
                    orders.append(
                        Order(
                            signal_bar=i - 1,
                            signal_time=int(bars.open_time[i - 1]),
                            direction=side,
                            state="ignored_pyramid",
                        )
                    )
                    warnings["pyramidSkips"] = int(warnings["pyramidSkips"]) + 1
                else:
                    if position is not None:
                        close_position(i, exit_price_at_open(i, position.direction), "opposite", False)
                    open_position(i, side, i - 1)
                    if side == "long":
                        break  # tie-break: long wins when both fire
        if idx_pos == len(in_range) - 1:
            for side in ("long", "short"):
                if direction != "both" and direction != side:
                    continue
                if decided(i, side):
                    orders.append(
                        Order(signal_bar=i, signal_time=cur_time, direction=side, state="expired_end_of_data")
                    )

        # --- intrabar phase: stops / targets, then trailing ratchet ---
        if position is not None:
            s = position.stop
            t = position.target
            # A stop level moved by the trailing ratchet keeps its identity:
            # exits off a trailed stop are labeled "trailing", not "stop".
            stop_reason = "trailing" if position.trail_level is not None else "stop"
            if position.direction == "long":
                s_px = s - spread_amt(s) - slip_amt(s)
                t_px = (t - spread_amt(t) - slip_amt(t)) if t is not None else None
                hit_stop = l <= s
                hit_tgt = t is not None and h >= t
                if hit_stop and hit_tgt:
                    warnings["ambiguousBars"] = int(warnings["ambiguousBars"]) + 1
                    close_position(i, s_px, stop_reason, True)
                elif hit_stop:
                    close_position(i, s_px, stop_reason, False)
                elif hit_tgt and t_px is not None:
                    close_position(i, t_px, "target", False)
            else:
                s_px = s + spread_amt(s) + slip_amt(s)
                t_px = (t + spread_amt(t) + slip_amt(t)) if t is not None else None
                hit_stop = h >= s
                hit_tgt = t is not None and l <= t
                if hit_stop and hit_tgt:
                    warnings["ambiguousBars"] = int(warnings["ambiguousBars"]) + 1
                    close_position(i, s_px, stop_reason, True)
                elif hit_stop:
                    close_position(i, s_px, stop_reason, False)
                elif hit_tgt and t_px is not None:
                    close_position(i, t_px, "target", False)
            if position is not None and position.trail_mult is not None and atr_id is not None:
                atr_now = float(values[atr_id].values["value"][i])
                if atr_now == atr_now and position.stop_distance > 0:
                    mult_d = money(atr_now) * money(position.trail_mult)
                    act = position.stop_distance * Decimal(str(position.trail_activation_r))
                    if position.direction == "long":
                        if h - position.entry_price >= act:
                            candidate = h - mult_d
                            base = position.trail_level if position.trail_level is not None else position.stop
                            position.trail_level = max(base, candidate)
                            position.stop = position.trail_level
                    else:
                        if position.entry_price - l >= act:
                            candidate = l + mult_d
                            base = position.trail_level if position.trail_level is not None else position.stop
                            position.trail_level = min(base, candidate)
                            position.stop = position.trail_level

        unrealized = Decimal("0")
        if position is not None:
            if position.direction == "long":
                unrealized = (c - position.entry_price) * position.qty
            else:
                unrealized = (position.entry_price - c) * position.qty
        equity.append((cur_time, cash + unrealized))

    if position is not None:
        last = in_range[-1]
        close_position(last, money(bars.close[last]), "end-of-data", False)

    assumptions = [
        f"{ENGINE_VERSION}: closed-bar signals, next-open fills",
        f"costs: {config.costs.spread_bps}bps spread, {config.costs.slippage_bps}bps slippage, "
        f"{config.costs.commission_per_unit}/unit commission (exit side: longs at bid)",
        f"ambiguity rule: stop-first; ambiguous bars: {warnings['ambiguousBars']}",
        "marginCallSimulated: false (leverage is a cap, not a margin simulator)",
        f"sizing: risk {risk['riskPerTradePct']}% of equity, estimate-vs-fill disclosed per trade",
        "short signals mirror long logic (>,<,>=,<=,crosses swapped); long wins ties",
    ]
    return RunPayload(
        trades=trades,
        orders=orders,
        equity=equity,
        warnings=warnings,
        assumptions=assumptions,
        engine_version=ENGINE_VERSION,
    )
