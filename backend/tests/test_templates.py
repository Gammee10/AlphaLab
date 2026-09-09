"""Templates: defaults validate, params bounded, fixtures pin determinism."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphalab_contracts import validate_spec
from alphalab_core.templates import TEMPLATES, describe, instantiate

FIXTURES = Path(__file__).parent / "fixtures" / "templates"


def test_all_defaults_validate() -> None:
    for tid in TEMPLATES:
        assert validate_spec(instantiate(tid, {})) == [], tid


def test_template_versions_pinned() -> None:
    assert {tid: TEMPLATES[tid]["version"] for tid in TEMPLATES} == {
        "trend-pullback": "1.0",
        "breakout-donchian": "1.0",
        "mean-reversion-bollinger": "1.0",
        "momentum-rsi": "1.0",
    }


def test_param_bounds() -> None:
    with pytest.raises(ValueError):
        instantiate("trend-pullback", {"riskPct": 99})
    with pytest.raises(ValueError):
        instantiate("trend-pullback", {"fastEma": 1})
    with pytest.raises(ValueError):
        instantiate("momentum-rsi", {"entry": 40, "exit": 45})
    with pytest.raises(ValueError):
        instantiate("nope", {})
    spec = instantiate("trend-pullback", {"direction": "short", "slAtr": 2.0})
    assert spec["entry"]["direction"] == "short"
    assert spec["exits"]["stopLoss"] == {"kind": "atr", "atrMultiplier": 2.0}
    assert validate_spec(spec) == []


def test_describe_grounds_in_spec() -> None:
    text = describe("trend-pullback", {})
    assert "EURUSD" in text and "0.5%" in text and "pullback" in text
    assert "emaFast" in text


def test_fixtures_match_fresh_instantiation() -> None:
    for tid in TEMPLATES:
        path = FIXTURES / f"{tid}.json"
        assert path.exists(), f"missing fixture for {tid}"
        stored = json.loads(path.read_text(encoding="utf-8"))
        assert stored == instantiate(tid, {})
        assert validate_spec(stored) == []
