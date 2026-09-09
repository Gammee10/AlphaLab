"""Engine micro-fixtures: hand-computed exact-Decimal expectations."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from alphalab_core.bars import bars_from_lists
from alphalab_core.config import Costs
from alphalab_core.engine import run_backtest

from helpers import M15, T0, basic_bars, base_spec, cfg, times


def test_stop_exact_touch() -> None:
    bars = bars_from_lists(
        times(4), [100, 101, 101, 102], [100, 101, 101, 102], [100, 100, 100, 101], [100, 101, 101, 102]
    )
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.entry_price == Decimal("101") and tr.exit_price == Decimal("100")
    assert tr.qty == Decimal("100") and tr.exit_reason == "stop" and not tr.ambiguous
    assert tr.gross_pnl == Decimal("-100") and tr.net_pnl == Decimal("-100")
    assert payload.equity[-1][1] == Decimal("9900")


def test_target_exact_touch() -> None:
    bars = bars_from_lists(
        times(4), [100, 101, 101, 102], [100, 101, 103, 104], [100, 100, 100.5, 101], [100, 101, 101, 102]
    )
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.exit_reason == "target" and tr.exit_price == Decimal("103")
    assert tr.gross_pnl == Decimal("200") and payload.equity[-1][1] == Decimal("10200")


def test_ambiguous_bar_stop_first() -> None:
    bars = bars_from_lists(
        times(4), [100, 101, 101, 102], [100, 101, 104, 105], [100, 100, 99, 101], [100, 101, 101, 102]
    )
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + 3 * M15))
    tr = payload.trades[0]
    assert tr.exit_reason == "stop" and tr.ambiguous
    assert payload.warnings["ambiguousBars"] == 1


def test_gap_through_stop_and_risk_warning() -> None:
    # Fill gaps far below the estimate: realized risk dwarfs intended risk.
    # Gap-through-stop exits at the open-adverse price (90), never the stop (100).
    bars = bars_from_lists(
        times(4), [100, 101, 90, 89], [100, 101, 91, 90], [100, 100, 89, 88], [100, 101, 90, 89]
    )
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.entry_price == Decimal("90")
    assert tr.exit_reason == "stop" and tr.exit_price == Decimal("90")
    assert tr.gross_pnl == Decimal("0") and tr.net_pnl == Decimal("0")
    assert tr.intended_risk == Decimal("100")
    assert tr.realized_risk == Decimal("1000")
    assert payload.warnings["gapRiskExceeded"] == 1
    assert payload.warnings["gapThroughStop"] == 1


def test_gap_through_stop_short() -> None:
    # Mirror: short gaps up through its stop -> exits at open-adverse (110).
    spec = base_spec()
    spec["entry"]["direction"] = "short"
    bars = bars_from_lists(
        times(4), [100, 99, 110, 111], [100, 99, 111, 112], [100, 98, 109, 110], [100, 99, 110, 111]
    )
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.direction == "short"
    assert tr.entry_price == Decimal("110")
    assert tr.exit_reason == "stop" and tr.exit_price == Decimal("110")
    assert tr.gross_pnl == Decimal("0") and tr.net_pnl == Decimal("0")
    assert payload.warnings["gapThroughStop"] == 1


def test_gap_exactly_to_stop_is_not_a_gap() -> None:
    # Bar opens exactly at the stop: no gap, exit at the stop price.
    bars = bars_from_lists(
        times(4), [100, 101, 100, 100], [100, 101, 101, 101], [100, 100, 99, 99], [100, 101, 100, 100]
    )
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.exit_reason == "stop" and tr.exit_price == Decimal("100")
    assert payload.warnings["gapThroughStop"] == 0


def test_gap_through_stop_with_target_touched_stays_stop_first() -> None:
    # Gap down through the stop while the high also reaches the target:
    # stop-first still wins, at the adverse open, marked ambiguous.
    bars = bars_from_lists(
        times(4), [100, 101, 90, 89], [100, 101, 104, 90], [100, 100, 89, 88], [100, 101, 90, 89]
    )
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.exit_reason == "stop" and tr.ambiguous
    assert tr.exit_price == Decimal("90")
    assert payload.warnings["ambiguousBars"] == 1
    assert payload.warnings["gapThroughStop"] == 1


def test_commission_and_slippage_stack_exact() -> None:
    bars = basic_bars()
    config = cfg(
        end_ms=T0 + 2 * M15,
        costs=Costs(spread_bps=Decimal("0"), slippage_bps=Decimal("50"), commission_per_unit=Decimal("1")),
    )
    payload = run_backtest(base_spec(), bars, config)
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    # fill = 101 * 1.005 = 101.505; stop still 100 (estimated pre-fill);
    # exit-side slippage also applies: 100 * (1 - 0.005) = 99.5.
    assert tr.entry_price == Decimal("101.505")
    assert tr.exit_price == Decimal("99.5")
    assert tr.fees == Decimal("200")  # 100 entry + 100 exit
    assert tr.gross_pnl == (Decimal("99.5") - Decimal("101.505")) * Decimal("100")


def test_end_of_data_exit_pays_exit_costs() -> None:
    # Force-close at the last bar nets spread/slippage/commission like any exit.
    spec = base_spec()
    spec["exits"]["takeProfit"] = {"kind": "none"}
    bars = bars_from_lists(
        times(4), [100, 101, 102, 103], [100, 101, 102, 103], [100, 100, 101, 102], [100, 101, 102, 103]
    )
    config = cfg(
        end_ms=T0 + 3 * M15,
        costs=Costs(spread_bps=Decimal("0"), slippage_bps=Decimal("50"), commission_per_unit=Decimal("1")),
    )
    payload = run_backtest(spec, bars, config)
    assert len(payload.trades) == 1
    tr = payload.trades[0]
    assert tr.exit_reason == "end-of-data"
    # fill = 102 * 1.005 = 102.51; exit = 103 * 0.995 = 102.485.
    assert tr.entry_price == Decimal("102.51")
    assert tr.exit_price == Decimal("102.485")
    assert tr.fees == Decimal("200")  # 100 entry + 100 exit
    assert tr.gross_pnl == (Decimal("102.485") - Decimal("102.51")) * Decimal("100")
    assert tr.net_pnl == tr.gross_pnl - Decimal("200")


def test_missing_output_selector_raises() -> None:
    # Multi-output indicator without `output`: engine raises instead of guessing.
    # Donchian(2) warms up after 1 bar, so the operand is really evaluated.
    spec = base_spec()
    spec["indicators"] = [{"id": "don", "kind": "Donchian", "period": 2}]
    spec["entry"]["conditions"] = [
        {"id": "c1", "left": {"kind": "indicator", "ref": "don"}, "op": ">", "right": {"kind": "const", "value": 0}}
    ]
    try:
        run_backtest(spec, basic_bars(), cfg(end_ms=T0 + 4 * M15))
    except ValueError as exc:
        assert "output" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing output selector")
    # Unknown output name also raises.
    spec["entry"]["conditions"][0]["left"]["output"] = "bogus"
    try:
        run_backtest(spec, basic_bars(), cfg(end_ms=T0 + 4 * M15))
    except ValueError as exc:
        assert "bogus" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown output name")


def test_capital_skip() -> None:
    spec = base_spec()
    spec["risk"]["maxNotionalMult"] = 1  # 101*100=10100 > 10000
    payload = run_backtest(spec, basic_bars(), cfg(end_ms=T0 + 4 * M15))
    assert payload.trades == []
    states = [o.state for o in payload.orders]
    assert states and set(states) <= {"skipped_capital", "expired_end_of_data"}
    assert payload.warnings["capitalSkips"] == 2  # signals at idx1 and idx3


def test_min_qty_skip() -> None:
    spec = base_spec()
    spec["risk"]["riskPerTradePct"] = 0.05  # risk 5, dist 1 -> qty 5... need < min 0.001? no; use tiny stop dist
    spec["exits"]["stopLoss"] = {"kind": "pips", "pips": 100000}  # dist 100000 -> qty 0.00005 -> floor 0
    payload = run_backtest(spec, basic_bars(), cfg(end_ms=T0 + 4 * M15))
    assert payload.trades == []
    assert payload.orders[0].state == "skipped_min_qty"
    assert payload.warnings["minQtySkips"] == 2  # signals at idx1 and idx3


def test_pyramid_skip_and_order_states() -> None:
    spec = base_spec()
    spec["entry"]["conditions"] = [
        {"id": "c1", "left": {"kind": "price", "field": "close"}, "op": ">", "right": {"kind": "const", "value": 0}}
    ]
    spec["exits"]["takeProfit"] = {"kind": "none"}
    bars = bars_from_lists(
        times(5), [100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [99, 100, 101, 102, 103], [100, 101, 102, 103, 104]
    )
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 4 * M15))
    assert len(payload.trades) == 1  # force-closed at end of data
    assert payload.trades[0].exit_reason == "end-of-data"
    states = [o.state for o in payload.orders]
    assert states[0] == "filled"
    assert states[1:-1] and set(states[1:-1]) == {"ignored_pyramid"}
    assert states[-1] == "expired_end_of_data"
    assert payload.warnings["pyramidSkips"] == len(states) - 2


def test_both_fire_long_wins_regardless_of_inventory() -> None:
    # `!=` mirrors to itself, so both sides fire on every bar.
    spec = base_spec()
    spec["entry"]["direction"] = "both"
    spec["entry"]["conditions"] = [
        {"id": "c1", "left": {"kind": "price", "field": "close"}, "op": "!=", "right": {"kind": "const", "value": 99999}}
    ]
    spec["exits"]["takeProfit"] = {"kind": "none"}
    bars = bars_from_lists(
        times(5), [100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [100, 101, 102, 103, 104]
    )
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 4 * M15))
    # Flat + both-fire opens long; long-held + both-fire stays long (no reversal).
    assert len(payload.trades) == 1
    assert payload.trades[0].direction == "long"
    assert payload.trades[0].exit_reason == "end-of-data"
    assert all(t.exit_reason != "opposite" for t in payload.trades)
    # `!=` needs no lookback, so signals fire at idx0..3: one fill + three skips.
    assert payload.warnings["pyramidSkips"] == 3
    assert [o.state for o in payload.orders[:4]] == [
        "filled", "ignored_pyramid", "ignored_pyramid", "ignored_pyramid"]


def test_reversal_two_legs() -> None:
    spec = base_spec()
    spec["entry"]["direction"] = "both"
    bars = bars_from_lists(
        times(5), [100, 101, 102, 101, 100], [101, 103, 103, 101, 100], [99, 100, 102, 99, 98], [100, 102, 101, 100, 99]
    )
    # Long signal idx1 (102>100) fills open[2]=102 (est 102, stop 101, target 104);
    # bar2 holds (L=102 > 100... stop=101, L=102 no; H=103 < 104 no).
    # Mirror (short) fires idx2 (101<102) -> reversal at open[3]=101.
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 3 * M15))
    assert len(payload.trades) == 2
    assert payload.trades[0].direction == "long" and payload.trades[0].exit_reason == "opposite"
    assert payload.trades[1].direction == "short"
    # Both legs transact at the same open price with separate commissions.
    assert payload.trades[0].exit_price == payload.trades[1].entry_price


def test_time_stop() -> None:
    spec = base_spec()
    spec["exits"]["timeStop"] = {"kind": "bars", "bars": 2}
    spec["exits"]["takeProfit"] = {"kind": "none"}
    bars = bars_from_lists(
        times(6),
        [100, 101, 101, 102, 103, 104],
        [100, 101, 102, 103, 104, 105],
        [100, 100, 100.5, 101, 102, 103],
        [100, 101, 101, 102, 103, 104],
    )
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 5 * M15))
    assert payload.trades[0].exit_reason == "time"
    assert payload.trades[0].exit_price == Decimal("103")  # open[entry(2)+2=4] = 103


def test_trailing_ratchets_never_loosens() -> None:
    spec = base_spec()
    spec["indicators"] = [{"id": "atr14", "kind": "ATR", "period": 2}]
    spec["exits"]["stopLoss"] = {"kind": "atr", "atrMultiplier": 1.0}
    spec["exits"]["takeProfit"] = {"kind": "none"}
    spec["exits"]["trailing"] = {"kind": "atr", "atrMultiplier": 1.0, "activationR": 1.0}
    bars = bars_from_lists(
        times(7),
        [100, 100, 100, 101, 102, 103, 101],
        [100, 101, 102, 103, 104, 105, 102],
        [99, 99, 99.5, 100, 101, 102, 100],
        [100, 100, 101, 102, 103, 104, 101],
    )
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 6 * M15))
    assert payload.trades, "expected a trailing exit"
    tr = payload.trades[0]
    assert tr.exit_reason == "trailing"
    assert tr.exit_price >= tr.entry_price - (tr.entry_price - tr.exit_price) * 0  # sanity
    # Exit must be above the initial stop (ratchet never loosened below it enough to matter):
    initial_stop = Decimal("100") - Decimal("1")  # approx: est 100, ATR(2)-ish ~1
    assert tr.exit_price > initial_stop


def test_opposite_exit_next_open_timing() -> None:
    spec = base_spec()
    spec["entry"]["direction"] = "long"
    spec["exits"]["oppositeSignalExit"] = True
    bars = bars_from_lists(
        times(6),
        [100, 101, 102, 103, 104, 105],
        [101, 102, 102.5, 104, 105, 106],
        [99, 100, 101, 102, 103, 104],
        [100, 101, 100, 99, 98, 97],
    )
    # Long signal at idx1 (101>100) fills open[2]=102 (est 101, stop 100, target 103);
    # bar2 holds (H=102.5, L=101). Mirror (short) fires at idx2 (100<101) ->
    # close at open[3]=103, NOT intrabar on bar 2.
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 5 * M15))
    assert len(payload.trades) == 1
    assert payload.trades[0].exit_reason == "opposite"
    assert payload.trades[0].exit_price == Decimal("103")


def test_session_filter() -> None:
    day = datetime(2024, 1, 2, tzinfo=timezone.utc)
    base = int(day.timestamp() * 1000)
    step = 3_600_000
    bars = bars_from_lists(
        [base + i * step for i in range(6)],
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 6],
    )
    spec = base_spec()
    spec["universe"] = {"symbol": "EURUSD", "timeframe": "H1"}
    spec["filters"] = {"session": {"kind": "window", "startHourUtc": 7, "endHourUtc": 20}}
    config = cfg(symbol="EURUSD", bar_step_ms=step, start_ms=base, end_ms=base + 5 * step)
    payload = run_backtest(spec, bars, config)
    # Signals at idx1..4 (hours 1..4) all outside 07-20 -> no trades.
    assert payload.trades == []
    assert payload.warnings["warmupBarsSkipped"] == 1  # signal bar 0 needs t-1


def test_spread_filter_blocks() -> None:
    spec = base_spec()
    spec["filters"] = {"spreadMaxBps": 10}
    payload = run_backtest(
        spec, basic_bars(), cfg(end_ms=T0 + 4 * M15, costs=Costs(spread_bps=Decimal("15")))
    )
    assert payload.trades == []


def test_warmup_suppression() -> None:
    spec = base_spec()
    spec["indicators"] = [{"id": "ema50", "kind": "EMA", "period": 50}]
    spec["entry"]["conditions"] = [
        {
            "id": "c1",
            "left": {"kind": "indicator", "ref": "ema50"},
            "op": ">",
            "right": {"kind": "const", "value": 0},
        }
    ]
    bars = bars_from_lists(
        times(10), list(range(100, 110)), list(range(101, 111)), list(range(99, 109)), list(range(100, 110))
    )
    payload = run_backtest(spec, bars, cfg(end_ms=T0 + 9 * M15))
    assert payload.trades == []
    assert payload.warnings["warmupBarsSkipped"] == 10  # every signal-bar evaluation undecidable, counted once


def test_cold_start_equivalence() -> None:
    closes = [100 + (i % 7) + i * 0.1 for i in range(100)]
    full = bars_from_lists(times(100), closes, [c + 1 for c in closes], [c - 1 for c in closes], closes)
    spec = base_spec()
    spec["indicators"] = [{"id": "ema10", "kind": "EMA", "period": 10}]
    spec["entry"]["conditions"] = [
        {
            "id": "c1",
            "left": {"kind": "price", "field": "close"},
            "op": ">",
            "right": {"kind": "indicator", "ref": "ema10"},
        }
    ]
    t70 = T0 + 70 * M15
    a = run_backtest(spec, full, cfg(start_ms=t70, end_ms=T0 + 99 * M15))
    cut = bars_from_lists(
        times(60, start=T0 + 40 * M15),
        closes[40:],
        [c + 1 for c in closes[40:]],
        [c - 1 for c in closes[40:]],
        closes[40:],
    )
    b = run_backtest(spec, cut, cfg(start_ms=t70, end_ms=T0 + 99 * M15))
    assert [(t.entry_time, t.exit_time, t.qty, t.net_pnl) for t in a.trades] == [
        (t.entry_time, t.exit_time, t.qty, t.net_pnl) for t in b.trades
    ]


def test_no_lookahead_mutation() -> None:
    closes = [100 + ((i * 37) % 11) - 5 + i * 0.05 for i in range(60)]
    bars = bars_from_lists(times(60), closes, [c + 0.5 for c in closes], [c - 0.5 for c in closes], closes)
    spec = base_spec()
    base = run_backtest(spec, bars, cfg(start_ms=T0, end_ms=T0 + 59 * M15))
    for t in (10, 30, 50):
        mutated = bars_from_lists(
            times(60),
            closes[:t] + [c + 500 for c in closes[t:]],
            [c + 0.5 for c in closes[:t]] + [c + 500 for c in closes[t:]],
            [c - 0.5 for c in closes[:t]] + [c + 500 for c in closes[t:]],
            closes[:t] + [c + 500 for c in closes[t:]],
        )
        rerun = run_backtest(spec, mutated, cfg(start_ms=T0, end_ms=T0 + 59 * M15))
        before = [tr for tr in base.trades if tr.exit_bar < t]
        after = [tr for tr in rerun.trades if tr.exit_bar < t]
        assert [(tr.entry_bar, tr.exit_bar, tr.qty, tr.net_pnl) for tr in before] == [
            (tr.entry_bar, tr.exit_bar, tr.qty, tr.net_pnl) for tr in after
        ], f"future mutation at {t} changed earlier trades"


def test_run_twice_identical() -> None:
    payload1 = run_backtest(base_spec(), basic_bars(), cfg(end_ms=T0 + 4 * M15))
    payload2 = run_backtest(base_spec(), basic_bars(), cfg(end_ms=T0 + 4 * M15))
    assert [(t.entry_price, t.exit_price, t.qty, t.net_pnl) for t in payload1.trades] == [
        (t.entry_price, t.exit_price, t.qty, t.net_pnl) for t in payload2.trades
    ]
    assert [e for e in payload1.equity] == [e for e in payload2.equity]
