"""Patch atomicity + ruled-provider tests (deterministic, no network)."""

from __future__ import annotations

import pytest

from alphalab_ai import ruled
from alphalab_contracts import validate_spec
from alphalab_core.patch import MAX_OPS, PatchError, apply_patch
from helpers import base_spec


def test_set_param_and_risk() -> None:
    spec = base_spec()
    spec["exits"]["stopLoss"] = {"kind": "atr", "atrMultiplier": 1.0}
    out = apply_patch(spec, [
        {"op": "setParam", "target": "exits.stopLoss.atrMultiplier", "value": 2.0},
        {"op": "setRisk", "field": "riskPerTradePct", "value": 0.25},
    ])
    assert out["exits"]["stopLoss"] == {"kind": "atr", "atrMultiplier": 2.0}
    assert out["risk"]["riskPerTradePct"] == 0.25
    assert spec["exits"]["stopLoss"] == {"kind": "atr", "atrMultiplier": 1.0}  # base untouched


def test_indicator_param_target() -> None:
    spec = base_spec()
    spec["indicators"] = [{"id": "ema10", "kind": "EMA", "period": 10}]
    out = apply_patch(spec, [{"op": "setParam", "target": "indicators.ema10.period", "value": 20}])
    assert out["indicators"][0]["period"] == 20
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "setParam", "target": "indicators.ema10.stdDev", "value": 2}])
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "setParam", "target": "exits.stopLoss.nope", "value": 1}])


def test_add_remove_condition_atomic() -> None:
    spec = base_spec()
    cond = {"id": "c9", "left": {"kind": "price", "field": "close"}, "op": ">",
            "right": {"kind": "const", "value": 50}}
    out = apply_patch(spec, [{"op": "addCondition", "condition": cond}])
    assert len(out["entry"]["conditions"]) == 2
    out2 = apply_patch(out, [{"op": "removeCondition", "id": "c9"}])
    assert len(out2["entry"]["conditions"]) == 1
    # Failure leaves the base untouched and raises.
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "removeCondition", "id": "missing"}])
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "addCondition", "condition": dict(cond, id="c1")}])
    assert len(spec["entry"]["conditions"]) == 1


def test_group_ops_and_limits() -> None:
    spec = base_spec()
    out = apply_patch(spec, [{"op": "addGroup", "id": "g1", "logic": "any",
                              "children": [{"id": "c9", "left": {"kind": "price", "field": "close"},
                                            "op": ">", "right": {"kind": "const", "value": 1}}]}])
    assert out["entry"]["conditions"][-1]["group"] == "any"
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "addGroup", "id": "g1", "logic": "maybe", "children": []}])
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "nope"}])
    with pytest.raises(PatchError):
        apply_patch(spec, [{"op": "setRisk", "field": "riskPerTradePct", "value": 1}] * (MAX_OPS + 1))


def test_ruled_intents() -> None:
    spec = base_spec()
    spec["exits"]["stopLoss"] = {"kind": "atr", "atrMultiplier": 1.0}
    assert ruled.propose(spec, "change stop to 1.5 ATR")["ops"] == [
        {"op": "setParam", "target": "exits.stopLoss.atrMultiplier", "value": 1.5}]
    assert ruled.propose(spec, "only trade london and new york")["ops"][0]["filter"] == "session"
    assert ruled.propose(spec, "change risk to 2%")["ops"] == [
        {"op": "setRisk", "field": "riskPerTradePct", "value": 2.0}]
    assert ruled.propose(spec, "add a volatility filter")["rationale"] == "clarifier"
    assert ruled.propose(spec, "do something mystical")["rationale"] == "clarifier"
    assert ruled.propose(spec, "remove the sma condition")["rationale"] == "clarifier"
    out = ruled.propose(spec, "remove the close condition")
    assert out["ops"] and all(o["op"] == "removeCondition" for o in out["ops"])


def test_ruled_explain_and_summarize() -> None:
    explanation = ruled.explain(base_spec())
    assert "BTCUSD" in explanation["text"] and explanation["provider"] == "ruled"
    summary = ruled.summarize(
        {"tradeCount": 10, "netProfit": "-50", "winRate": 0.7, "profitFactor": 0.8,
         "maxDrawdown": "200", "maxDrawdownPct": 2.0},
        {"ambiguousBars": 2, "capitalSkips": 0}, ["r1"])
    assert "profit factor below 1" in summary["text"]
    assert summary["citations"] and summary["provider"] == "ruled"
