"""Rule-based assistant: deterministic offline provider (docs/ai-assistant.md).

Keyword-to-patch mapping with clarifier fallback. Every response carries
provider/model metadata so the UI banner stays honest.
"""

from __future__ import annotations

import re
from typing import Any

PROVIDER = "ruled"
MODEL = "ruled/1.0"


def _num_after(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def propose(spec: dict[str, Any] | None, intent: str) -> dict[str, Any]:
    """Build a StrategyPatch dict (unvalidated here; caller validates)."""
    text = intent.lower()
    ops: list[dict[str, Any]] = []
    notes: list[str] = []

    stop = _num_after(r"stop(?:\s*loss)?(?:\s*(?:to|of|=))?\s*(\d+(?:\.\d+)?)\s*atr", text)
    if stop is not None and spec is not None and spec.get("exits", {}).get("stopLoss", {}).get("kind") == "atr":
        ops.append({"op": "setParam", "target": "exits.stopLoss.atrMultiplier", "value": stop})
        notes.append(f"stop to {stop} ATR")
    target = _num_after(r"(?:target|take profit|take-profit|tp)(?:\s*(?:to|of|=|at))?\s*(\d+(?:\.\d+)?)\s*r?\b", text)
    if target is not None and spec is not None and spec.get("exits", {}).get("takeProfit", {}).get("kind") == "rr":
        ops.append({"op": "setParam", "target": "exits.takeProfit.ratio", "value": target})
        notes.append(f"target to {target}R")
    risk = _num_after(r"risk(?:\s*(?:to|of|=|at|per trade))?\s*(\d+(?:\.\d+)?)\s*%?", text)
    if risk is not None and "stop" not in text and "target" not in text and "profit" not in text:
        ops.append({"op": "setRisk", "field": "riskPerTradePct", "value": risk})
        notes.append(f"risk to {risk}%")
    if any(k in text for k in ("london", "new york", "session", "trade between", "only trade")):
        ops.append({"op": "addFilter", "filter": "session",
                    "value": {"kind": "window", "startHourUtc": 7, "endHourUtc": 20}})
        notes.append("session 07-20 UTC")
    if "volatility filter" in text or "volatility" in text:
        return {"ops": [], "rationale": "clarifier",
                "message": "Which ATR bounds? Reply e.g. 'volatility filter min 0.001 max 0.01'."}
    remove = re.search(r"remove\s+(?:the\s+)?(\w+)", text)
    if remove and spec is not None:
        needle = remove.group(1).lower()
        hits = [
            c["id"] for c in _leaves(spec.get("entry", {}).get("conditions", []))
            if needle in _cond_text(c).lower()
        ]
        if hits:
            ops.extend({"op": "removeCondition", "id": h} for h in hits)
            notes.append(f"removed {', '.join(hits)}")
    if not ops:
        return {"ops": [], "rationale": "clarifier",
                "message": "I couldn't map that to a concrete change. Try e.g. 'change stop to 1.5 ATR'."}
    return {"ops": ops, "rationale": "; ".join(notes)}


def _leaves(conditions: list[Any]) -> list[dict[str, Any]]:
    out = []
    for node in conditions:
        if isinstance(node, dict) and "group" in node:
            out.extend(_leaves(node.get("children", [])))
        elif isinstance(node, dict):
            out.append(node)
    return out


def _cond_text(cond: dict[str, Any]) -> str:
    parts = []
    for side in ("left", "right"):
        op = cond.get(side, {})
        if op.get("kind") == "indicator":
            parts.append(str(op.get("ref", "")))
        elif op.get("kind") == "price":
            parts.append(str(op.get("field", "")))
    return " ".join(parts)


def explain(spec: dict[str, Any]) -> dict[str, Any]:
    from alphalab_core.templates import describe_node

    universe = spec.get("universe", {})
    lines = [
        f"Strategy on {universe.get('symbol')} {universe.get('timeframe')} "
        f"({spec.get('entry', {}).get('direction')} entries):"
    ]
    for cond in spec.get("entry", {}).get("conditions", []):
        lines.append(f"- {describe_node(cond)}")
    exits = spec.get("exits", {})
    lines.append(f"- Stop: {_exit_text(exits.get('stopLoss', {}))}; Target: {_exit_text(exits.get('takeProfit', {}))}")
    lines.append(f"- Risk per trade: {spec.get('risk', {}).get('riskPerTradePct')}%")
    lines.append("- Fills at next open with configured spread/slippage/commission; stops pessimistic (stop-first).")
    return {"text": "\n".join(lines), "citations": ["spec"], "provider": PROVIDER, "model": MODEL}


def _exit_text(exit: dict[str, Any]) -> str:
    kind = exit.get("kind")
    if kind == "atr":
        return f"{exit.get('atrMultiplier')}x ATR"
    if kind == "pips":
        return f"{exit.get('pips')} pips"
    if kind == "rr":
        return f"{exit.get('ratio')}R"
    return "none"


def summarize(metrics: dict[str, Any], warnings: dict[str, Any], run_ids: list[str]) -> dict[str, Any]:
    n = metrics.get("tradeCount", 0)
    lines = [
        f"Across {len(run_ids)} run(s): {n} trades, net {metrics.get('netProfit')}, "
        f"win rate {metrics.get('winRate')}, profit factor {metrics.get('profitFactor')}, "
        f"max drawdown {metrics.get('maxDrawdown')} ({metrics.get('maxDrawdownPct')}%)."
    ]
    pf = metrics.get("profitFactor")
    wr = metrics.get("winRate")
    if wr is not None and pf is not None and wr > 0.5 and pf < 1:
        lines.append("Heuristic: high win rate with profit factor below 1 means average loss dominates — "
                     "review stop distance and reward-to-risk.")
    if warnings.get("ambiguousBars"):
        lines.append(f"Heuristic: {warnings['ambiguousBars']} ambiguous bar(s) resolved stop-first (pessimistic).")
    if warnings.get("capitalSkips"):
        lines.append(f"Heuristic: {warnings['capitalSkips']} entries skipped on capital limits — sizing may be aggressive.")
    if n < 30:
        lines.append("Heuristic: fewer than 30 trades — treat all ratios as descriptive, not predictive.")
    return {"text": "\n".join(lines), "citations": ["metrics.tradeCount", "metrics.netProfit",
            "metrics.profitFactor", "metrics.maxDrawdown"], "provider": PROVIDER, "model": MODEL}
