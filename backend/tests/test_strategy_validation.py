import copy

import pytest

from alphalab_contracts import (
    NotSupportedError,
    StrategyInvalidError,
    check_run_compatibility,
    spec_hash,
    validate_spec,
    validate_spec_or_raise,
)


def valid_spec() -> dict:
    return {
        "specVersion": "1.0",
        "universe": {"symbol": "EURUSD", "timeframe": "M15"},
        "indicators": [
            {"id": "ema50", "kind": "EMA", "period": 50},
            {"id": "ema200", "kind": "EMA", "period": 200},
            {"id": "ema20", "kind": "EMA", "period": 20},
            {"id": "atr14", "kind": "ATR", "period": 14},
        ],
        "entry": {
            "direction": "long",
            "logic": "all",
            "conditions": [
                {
                    "id": "c1",
                    "left": {"kind": "indicator", "ref": "ema50"},
                    "op": ">",
                    "right": {"kind": "indicator", "ref": "ema200"},
                },
                {
                    "id": "c2",
                    "left": {"kind": "price", "field": "close"},
                    "op": "<",
                    "right": {"kind": "indicator", "ref": "ema20"},
                },
                {
                    "id": "c3",
                    "left": {"kind": "price", "field": "close"},
                    "op": ">",
                    "right": {"kind": "price", "field": "close", "offsetBars": 1},
                },
            ],
        },
        "exits": {
            "stopLoss": {"kind": "atr", "atrMultiplier": 1.5},
            "takeProfit": {"kind": "rr", "ratio": 2},
            "trailing": {"kind": "none"},
            "timeStop": {"kind": "none"},
            "oppositeSignalExit": True,
        },
        "filters": {
            "session": {"kind": "window", "startHourUtc": 7, "endHourUtc": 20},
            "volatility": {"kind": "none"},
            "spreadMaxBps": 25,
        },
        "risk": {"riskPerTradePct": 0.5, "maxNotionalMult": 3, "leverageMax": 10},
        "execution": {"fillBasis": "next_open"},
    }


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def test_valid_spec_passes_and_hashes() -> None:
    spec = valid_spec()
    assert validate_spec(spec) == []
    assert validate_spec_or_raise(spec) is spec
    h1 = spec_hash(spec)
    assert len(h1) == 64
    # Deterministic across key order.
    shuffled = dict(reversed(list(spec.items())))
    assert spec_hash(shuffled) == h1


def test_reserved_future_absent_equals_empty() -> None:
    a = valid_spec()
    b = valid_spec()
    b["reservedForFuture"] = {}
    assert validate_spec(b) == []
    assert spec_hash(a) == spec_hash(b)


def test_canonical_numeric_rounding() -> None:
    a = valid_spec()
    b = valid_spec()
    b["risk"]["riskPerTradePct"] = 0.50000001
    assert validate_spec(b) == []
    assert spec_hash(a) == spec_hash(b)


def test_unknown_indicator_ref() -> None:
    spec = valid_spec()
    spec["entry"]["conditions"][0]["right"] = {"kind": "indicator", "ref": "ema999"}
    assert codes(validate_spec(spec)) == {"STRATEGY_INVALID"}


def test_duplicate_indicator_ids() -> None:
    spec = valid_spec()
    spec["indicators"].append({"id": "ema50", "kind": "SMA", "period": 10})
    assert "STRATEGY_INVALID" in codes(validate_spec(spec))


def test_negative_offset_is_lookahead() -> None:
    spec = valid_spec()
    spec["entry"]["conditions"][2]["right"] = {"kind": "price", "field": "close", "offsetBars": -1}
    found = codes(validate_spec(spec))
    assert "LOOKAHEAD_OFFSET_REJECTED" in found


def test_unknown_operand_kind_not_supported() -> None:
    spec = valid_spec()
    spec["entry"]["conditions"][0]["left"] = {"kind": "tick", "ref": "x"}
    assert "NOT_SUPPORTED_IN_MVP" in codes(validate_spec(spec))


def test_macd_fast_slow_order() -> None:
    spec = valid_spec()
    spec["indicators"] = [{"id": "m", "kind": "MACD", "fast": 26, "slow": 12, "signal": 9}]
    spec["entry"]["conditions"] = [
        {
            "id": "c1",
            "left": {"kind": "indicator", "ref": "m"},
            "op": ">",
            "right": {"kind": "const", "value": 0},
        }
    ]
    assert "STRATEGY_INVALID" in codes(validate_spec(spec))


def _leaf(i: int) -> dict:
    return {
        "id": f"c{i}",
        "left": {"kind": "price", "field": "close"},
        "op": ">",
        "right": {"kind": "const", "value": 100 + i},
    }


def test_group_depth_limit() -> None:
    spec = valid_spec()
    deep: dict = _leaf(1)
    for level in range(4):
        deep = {"id": f"g{level}", "group": "all", "children": [deep]}
    spec["entry"]["conditions"] = [deep]
    assert "STRATEGY_INVALID" in codes(validate_spec(spec))


def test_nested_groups_within_limits_pass() -> None:
    spec = valid_spec()
    spec["entry"]["conditions"] = [
        _leaf(1),
        {"id": "g1", "group": "any", "children": [_leaf(2), _leaf(3)]},
    ]
    assert validate_spec(spec) == []


def test_leaf_count_limit() -> None:
    spec = valid_spec()
    spec["entry"]["conditions"] = [_leaf(i) for i in range(13)]
    assert "STRATEGY_INVALID" in codes(validate_spec(spec))


def test_duplicate_condition_ids() -> None:
    spec = valid_spec()
    spec["entry"]["conditions"] = [_leaf(1), _leaf(1)]
    assert "STRATEGY_INVALID" in codes(validate_spec(spec))


def test_reserved_future_rejected() -> None:
    spec = valid_spec()
    spec["reservedForFuture"] = {"partials": True}
    assert codes(validate_spec(spec)) == {"NOT_SUPPORTED_IN_MVP"}
    with pytest.raises(NotSupportedError):
        validate_spec_or_raise(spec)


def test_session_window_on_d1_rejected() -> None:
    spec = valid_spec()
    spec["universe"]["timeframe"] = "D1"
    assert codes(validate_spec(spec)) == {"NOT_SUPPORTED_IN_MVP"}


def test_zero_length_session_rejected() -> None:
    spec = valid_spec()
    spec["filters"]["session"] = {"kind": "window", "startHourUtc": 8, "endHourUtc": 8}
    assert "STRATEGY_INVALID" in codes(validate_spec(spec))


def test_overnight_session_allowed() -> None:
    spec = valid_spec()
    spec["filters"]["session"] = {"kind": "window", "startHourUtc": 20, "endHourUtc": 7}
    assert validate_spec(spec) == []


def test_schema_ranges_and_enums() -> None:
    for mutate in (
        lambda s: s.update({"specVersion": "2.0"}),
        lambda s: s["universe"].update({"symbol": "AAPL"}),
        lambda s: s["risk"].update({"riskPerTradePct": 50}),
        lambda s: s["indicators"].append({"id": "x", "kind": "Supertrend", "period": 10}),
        lambda s: s["entry"].update({"conditions": []}),
    ):
        spec = valid_spec()
        mutate(spec)
        assert "STRATEGY_INVALID" in codes(validate_spec(spec)), mutate


def test_raise_wraps_invalid() -> None:
    spec = valid_spec()
    spec["risk"]["riskPerTradePct"] = 99
    with pytest.raises(StrategyInvalidError) as exc:
        validate_spec_or_raise(spec)
    assert exc.value.code == "STRATEGY_INVALID"


def test_vwap_needs_volume() -> None:
    spec = valid_spec()
    spec["indicators"] = [{"id": "v", "kind": "VWAP"}]
    spec["entry"]["conditions"] = [
        {
            "id": "c1",
            "left": {"kind": "indicator", "ref": "v"},
            "op": ">",
            "right": {"kind": "const", "value": 1},
        }
    ]
    assert validate_spec(spec) == []
    assert [i.code for i in check_run_compatibility(spec, has_volume=False)] == ["DATASET_INVALID"]
    assert check_run_compatibility(spec, has_volume=True) == []


def test_copy_isolation() -> None:
    # Guard: fixtures must not leak mutations between tests.
    assert valid_spec()["risk"]["riskPerTradePct"] == 0.5
    _ = copy.deepcopy(valid_spec())
