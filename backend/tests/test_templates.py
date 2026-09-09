"""Templates: defaults validate, params bounded, fixtures pin determinism."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from alphalab_contracts import validate_spec
from alphalab_core.config import BacktestConfig, Costs
from alphalab_core.engine import run_backtest
from alphalab_core.templates import TEMPLATES, describe, instantiate
from alphalab_marketdata import to_bar_arrays
from alphalab_marketdata.synthetic import generate_synthetic

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


def test_breakout_uses_prior_bar_channel() -> None:
    """Regression: current-bar-inclusive Donchian can never be crossed (close <=
    its own bar's high always). The template must offset to the prior bar."""
    spec = instantiate("breakout-donchian", {})
    for cond in spec["entry"]["conditions"]:
        assert cond["right"].get("offsetBars") == 1, cond["id"]


def test_all_defaults_trade_on_sample_data() -> None:
    """Every template must produce trades out-of-the-box (no silent zero-trade runs)."""
    rows = generate_synthetic("EURUSD", "M15", "2024-01-01T00:00:00Z", 400, 7, 1.1, volatility=0.0008)
    bars = to_bar_arrays(rows)
    for tid in TEMPLATES:
        spec = instantiate(tid, {})
        assert validate_spec(spec) == []
        cfg = BacktestConfig(
            symbol="EURUSD", bar_step_ms=900_000, start_ms=rows[0].open_time, end_ms=rows[-1].open_time,
            initial_capital=Decimal("10000"),
            costs=Costs(spread_bps=Decimal("15"), slippage_bps=Decimal("5"), commission_per_unit=Decimal("0")),
        )
        payload = run_backtest(spec, bars, cfg)
        assert len(payload.trades) > 0, f"{tid} produced zero trades on defaults"
