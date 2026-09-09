"""Strategy templates: versioned parameterized constructors (docs/templates.md).

Each template is a pure ``instantiate(params) -> StrategySpec`` plus a JSON
param schema (rendered by the web gallery) and a ``describe`` used for preview
and AI grounding. Templates are immutable: behavior changes ship as new
``template_version`` rows; instantiation provenance is recorded on the Strategy.
"""

from __future__ import annotations

from typing import Any


def _num(name: str, params: dict[str, Any], default: float, lo: float, hi: float) -> float:
    value = params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not lo <= float(value) <= hi:
        raise ValueError(f"{name} must be within [{lo}, {hi}]")
    return float(value)


def _int(name: str, params: dict[str, Any], default: int, lo: int, hi: int) -> int:
    value = params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ValueError(f"{name} must be an integer")
    if not lo <= int(value) <= hi:
        raise ValueError(f"{name} must be within [{lo}, {hi}]")
    return int(value)


def _direction(params: dict[str, Any], default: str, allowed: tuple[str, ...]) -> str:
    value = params.get("direction", default)
    if value not in allowed:
        raise ValueError(f"direction must be one of {allowed}")
    return str(value)


def _session_filter(params: dict[str, Any], default: tuple[int, int] | None) -> dict[str, Any]:
    if "sessionStart" in params or "sessionEnd" in params:
        s = _int("sessionStart", params, 0, 0, 24)
        e = _int("sessionEnd", params, 0, 0, 24)
        if s == e:
            raise ValueError("session window must have non-zero length")
        return {"kind": "window", "startHourUtc": s, "endHourUtc": e}
    if default is None:
        return {"kind": "none"}
    return {"kind": "window", "startHourUtc": default[0], "endHourUtc": default[1]}


def _base(symbol: str, timeframe: str, risk_pct: float) -> dict[str, Any]:
    return {
        "specVersion": "1.0",
        "universe": {"symbol": symbol, "timeframe": timeframe},
        "exits": {},
        "filters": {},
        "risk": {"riskPerTradePct": risk_pct, "maxNotionalMult": 3, "leverageMax": 10},
        "execution": {"fillBasis": "next_open"},
    }


def trend_pullback(params: dict[str, Any]) -> dict[str, Any]:
    """EMA trend + pullback entry + ATR stop + RR target."""
    fast = _int("fastEma", params, 50, 2, 500)
    slow = _int("slowEma", params, 200, 2, 500)
    pull = _int("pullbackEma", params, 20, 2, 500)
    atr_p = _int("atrPeriod", params, 14, 2, 100)
    sl = _num("slAtr", params, 1.5, 0.25, 10)
    rr = _num("rr", params, 2.0, 0.25, 10)
    direction = _direction(params, "long", ("long", "short"))
    risk_pct = _num("riskPct", params, 0.5, 0.05, 5)
    symbol = str(params.get("symbol", "EURUSD"))
    timeframe = str(params.get("timeframe", "M15"))
    spec = _base(symbol, timeframe, risk_pct)
    spec["indicators"] = [
        {"id": "emaFast", "kind": "EMA", "period": fast},
        {"id": "emaSlow", "kind": "EMA", "period": slow},
        {"id": "emaPull", "kind": "EMA", "period": pull},
        {"id": "atr", "kind": "ATR", "period": atr_p},
    ]
    trend_op = ">" if direction == "long" else "<"
    spec["entry"] = {
        "direction": direction,
        "logic": "all",
        "conditions": [
            {"id": "trend", "left": {"kind": "indicator", "ref": "emaFast"}, "op": trend_op,
             "right": {"kind": "indicator", "ref": "emaSlow"}},
            {"id": "pullback", "left": {"kind": "price", "field": "close"},
             "op": "<" if direction == "long" else ">", "right": {"kind": "indicator", "ref": "emaPull"}},
            {"id": "bounce", "left": {"kind": "price", "field": "close"},
             "op": ">" if direction == "long" else "<", "right": {"kind": "price", "field": "close", "offsetBars": 1}},
        ],
    }
    spec["exits"] = {
        "stopLoss": {"kind": "atr", "atrMultiplier": sl},
        "takeProfit": {"kind": "rr", "ratio": rr},
        "trailing": {"kind": "none"},
        "timeStop": {"kind": "none"},
        "oppositeSignalExit": True,
    }
    spec["filters"] = {"session": _session_filter(params, (7, 20)), "volatility": {"kind": "none"}}
    return spec


def breakout_donchian(params: dict[str, Any]) -> dict[str, Any]:
    """Donchian breakout both directions; mirror semantics resolve the side."""
    channel = _int("channel", params, 20, 2, 500)
    atr_p = _int("atrPeriod", params, 14, 2, 100)
    sl = _num("slAtr", params, 1.0, 0.25, 10)
    rr = _num("rr", params, 2.0, 0.25, 10)
    risk_pct = _num("riskPct", params, 0.5, 0.05, 5)
    symbol = str(params.get("symbol", "EURUSD"))
    timeframe = str(params.get("timeframe", "M15"))
    spec = _base(symbol, timeframe, risk_pct)
    spec["indicators"] = [
        {"id": "don", "kind": "Donchian", "period": channel},
        {"id": "atr", "kind": "ATR", "period": atr_p},
    ]
    spec["entry"] = {
        "direction": "both",
        "logic": "any",
        "conditions": [
            {"id": "breakUp", "left": {"kind": "price", "field": "close"}, "op": "crossesAbove",
             "right": {"kind": "indicator", "ref": "don", "output": "upper"}},
            {"id": "breakDown", "left": {"kind": "price", "field": "close"}, "op": "crossesBelow",
             "right": {"kind": "indicator", "ref": "don", "output": "lower"}},
        ],
    }
    spec["exits"] = {
        "stopLoss": {"kind": "atr", "atrMultiplier": sl},
        "takeProfit": {"kind": "rr", "ratio": rr},
        "trailing": {"kind": "none"},
        "timeStop": {"kind": "none"},
        "oppositeSignalExit": True,
    }
    spec["filters"] = {"session": {"kind": "none"}, "volatility": {"kind": "none"}}
    return spec


def mean_reversion_bollinger(params: dict[str, Any]) -> dict[str, Any]:
    """Fade BB extremes confirmed by RSI; mirror resolves the short side."""
    bb_p = _int("bbPeriod", params, 20, 2, 500)
    std = _num("stdDev", params, 2.0, 0.5, 4)
    rsi_p = _int("rsiPeriod", params, 14, 2, 100)
    rsi_low = _num("rsiLow", params, 30.0, 5, 45)
    rsi_high = _num("rsiHigh", params, 70.0, 55, 95)
    sl = _num("slAtr", params, 1.5, 0.25, 10)
    rr = _num("rr", params, 1.5, 0.25, 10)
    risk_pct = _num("riskPct", params, 0.5, 0.05, 5)
    symbol = str(params.get("symbol", "EURUSD"))
    timeframe = str(params.get("timeframe", "M15"))
    spec = _base(symbol, timeframe, risk_pct)
    spec["indicators"] = [
        {"id": "bb", "kind": "BB", "period": bb_p, "stdDev": std},
        {"id": "rsi", "kind": "RSI", "period": rsi_p},
        {"id": "atr", "kind": "ATR", "period": 14},
    ]
    spec["entry"] = {
        "direction": "both",
        "logic": "all",
        "conditions": [
            {"id": "outside", "left": {"kind": "price", "field": "close"}, "op": "<",
             "right": {"kind": "indicator", "ref": "bb", "output": "lower"}},
            {"id": "stretched", "left": {"kind": "indicator", "ref": "rsi"}, "op": "<",
             "right": {"kind": "const", "value": rsi_low}},
        ],
    }
    spec["exits"] = {
        "stopLoss": {"kind": "atr", "atrMultiplier": sl},
        "takeProfit": {"kind": "rr", "ratio": rr},
        "trailing": {"kind": "none"},
        "timeStop": {"kind": "none"},
        "oppositeSignalExit": True,
    }
    spec["filters"] = {"session": {"kind": "none"}, "volatility": {"kind": "none"}}
    return spec


def momentum_rsi(params: dict[str, Any]) -> dict[str, Any]:
    """RSI regime + trigger cross; mirror resolves the short side."""
    rsi_p = _int("rsiPeriod", params, 14, 2, 100)
    entry = _num("entry", params, 55.0, 50, 90)
    exit_ = _num("exit", params, 45.0, 10, 50)
    if not exit_ < entry:
        raise ValueError("exit must be below entry")
    sl = _num("slAtr", params, 2.0, 0.25, 10)
    rr = _num("rr", params, 2.0, 0.25, 10)
    risk_pct = _num("riskPct", params, 0.5, 0.05, 5)
    symbol = str(params.get("symbol", "EURUSD"))
    timeframe = str(params.get("timeframe", "M15"))
    spec = _base(symbol, timeframe, risk_pct)
    spec["indicators"] = [
        {"id": "rsi", "kind": "RSI", "period": rsi_p},
        {"id": "atr", "kind": "ATR", "period": 14},
    ]
    spec["entry"] = {
        "direction": "both",
        "logic": "all",
        "conditions": [
            {"id": "regime", "left": {"kind": "indicator", "ref": "rsi"}, "op": ">",
             "right": {"kind": "const", "value": exit_}},
            {"id": "trigger", "left": {"kind": "indicator", "ref": "rsi"}, "op": "crossesAbove",
             "right": {"kind": "const", "value": entry}},
        ],
    }
    spec["exits"] = {
        "stopLoss": {"kind": "atr", "atrMultiplier": sl},
        "takeProfit": {"kind": "rr", "ratio": rr},
        "trailing": {"kind": "none"},
        "timeStop": {"kind": "none"},
        "oppositeSignalExit": True,
    }
    spec["filters"] = {"session": {"kind": "none"}, "volatility": {"kind": "none"}}
    return spec


TEMPLATES: dict[str, dict[str, Any]] = {
    "trend-pullback": {
        "version": "1.0",
        "displayName": "Trend pullback",
        "description": "Trade with the EMA trend, enter on a pullback with confirmation.",
        "instantiate": trend_pullback,
    },
    "breakout-donchian": {
        "version": "1.0",
        "displayName": "Donchian breakout",
        "description": "Enter on Donchian channel breakouts in either direction.",
        "instantiate": breakout_donchian,
    },
    "mean-reversion-bollinger": {
        "version": "1.0",
        "displayName": "Bollinger mean reversion",
        "description": "Fade Bollinger extremes confirmed by RSI.",
        "instantiate": mean_reversion_bollinger,
    },
    "momentum-rsi": {
        "version": "1.0",
        "displayName": "RSI momentum",
        "description": "RSI regime filter with a trigger cross for continuation entries.",
        "instantiate": momentum_rsi,
    },
}


def instantiate(template_id: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        template = TEMPLATES[template_id]
    except KeyError:
        raise ValueError(f"unknown template: {template_id!r}") from None
    spec = template["instantiate"](dict(params))
    if not isinstance(spec, dict):
        raise ValueError("template must return a spec dict")
    return spec


def describe(template_id: str, params: dict[str, Any]) -> str:
    spec = instantiate(template_id, params)
    lines = [
        f"{TEMPLATES[template_id]['displayName']} on {spec['universe']['symbol']} {spec['universe']['timeframe']}:"
    ]
    entry = spec["entry"]
    lines.append(f"- Entries ({entry['direction']}, {entry['logic']}):")
    for cond in entry["conditions"]:
        lines.append(f"  - {describe_node(cond)}")
    sl, tp = spec["exits"]["stopLoss"], spec["exits"]["takeProfit"]
    lines.append(f"- Stop: {describe_exit(sl)}; Target: {describe_exit(tp)}")
    lines.append(f"- Risk per trade: {spec['risk']['riskPerTradePct']}%")
    return "\n".join(lines)


def describe_node(node: dict[str, Any]) -> str:
    if "group" in node:
        joiner = " AND " if node["group"] == "all" else " OR "
        return "(" + joiner.join(describe_node(c) for c in node["children"]) + ")"
    return f"{describe_operand(node['left'])} {node['op']} {describe_operand(node['right'])}"


def describe_operand(op: dict[str, Any]) -> str:
    kind = op["kind"]
    if kind == "const":
        return str(op["value"])
    if kind == "price":
        return str(op["field"])
    ref = str(op["ref"]) + (f".{op['output']}" if op.get("output") else "")
    offset = op.get("offsetBars", 0)
    return ref + (f"[{offset} bars ago]" if offset else "")


def describe_exit(exit: dict[str, Any]) -> str:
    kind = exit.get("kind")
    if kind == "atr":
        return f"{exit['atrMultiplier']}x ATR"
    if kind == "pips":
        return f"{exit['pips']} pips"
    if kind == "rr":
        return f"{exit['ratio']}R"
    return "none"
