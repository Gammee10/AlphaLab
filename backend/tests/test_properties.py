"""Property tests for engine guarantees (docs/testing.md).

Each property must hold for *every* input in its domain, not just the
hand-picked fixtures in test_engine.py:
- determinism: identical inputs -> bit-identical outputs;
- no-lookahead: mutating future bars never changes already-closed trades;
- accounting identity: final equity == capital + realized P&L (runs always
  end flat via end-of-data force-close);
- sizing discipline: every fill respects the instrument lot step/minimum.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from alphalab_core.bars import bars_from_lists
from alphalab_core.engine import run_backtest
from alphalab_core.instruments import get_instrument

from helpers import M15, T0, base_spec, cfg, times

# Tradable domain: around 100 so the 5x-notional cap does not skip every
# trade (uniform [1, 10000] closes average ~5000 and never fill).
CLOSES = st.lists(
    st.floats(min_value=50.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    min_size=5, max_size=40,
)

SETTINGS = settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _bars(closes: list[float]):
    n = len(closes)
    opens = [closes[0]] + closes[:-1]
    return bars_from_lists(
        times(n), opens, [c + 0.5 for c in closes], [c - 0.5 for c in closes], closes)


def _sig(payload) -> list:
    return [(t.entry_bar, t.exit_bar, t.direction, t.qty, t.entry_price, t.exit_price, t.net_pnl)
            for t in payload.trades]


@given(CLOSES)
@SETTINGS
def test_determinism_random_series(closes: list[float]) -> None:
    bars = _bars(closes)
    config = cfg(end_ms=T0 + (len(closes) - 1) * M15)
    first = run_backtest(base_spec(), bars, config)
    second = run_backtest(base_spec(), bars, config)
    assert _sig(first) == _sig(second)
    assert list(first.equity) == list(second.equity)
    assert first.warnings == second.warnings


@given(CLOSES)
@SETTINGS
def test_future_mutation_never_changes_closed_trades(closes: list[float]) -> None:
    n = len(closes)
    bars = _bars(closes)
    config = cfg(end_ms=T0 + (n - 1) * M15)
    base = run_backtest(base_spec(), bars, config)
    assume(len(base.trades) > 0)  # property is vacuous without closed trades
    # Mutate the tail from several cut points; earlier closed trades are fixed.
    for t in (5, n // 2, n - 2):
        if not 1 <= t < n:
            continue
        bumped = closes[:t] + [c + 500.0 for c in closes[t:]]
        rerun = run_backtest(base_spec(), _bars(bumped), config)
        before = [tr for tr in base.trades if tr.exit_bar < t]
        after = [tr for tr in rerun.trades if tr.exit_bar < t]
        assert _sig_for(before) == _sig_for(after), f"future mutation at {t} leaked"


def _sig_for(trades) -> list:
    return [(t.entry_bar, t.exit_bar, t.direction, t.qty, t.entry_price, t.exit_price, t.net_pnl)
            for t in trades]


@given(CLOSES)
@SETTINGS
def test_flat_close_accounting_identity(closes: list[float]) -> None:
    # Every run ends flat (end-of-data force-close), so final equity must
    # equal initial capital plus realized net P&L -- exactly, in Decimal.
    bars = _bars(closes)
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + (len(closes) - 1) * M15))
    if not payload.equity:
        return
    realized = sum((t.net_pnl for t in payload.trades), Decimal("0"))
    assert payload.equity[-1][1] == Decimal("10000") + realized


@given(CLOSES)
@SETTINGS
def test_qty_respects_lot_step(closes: list[float]) -> None:
    meta = get_instrument("BTCUSD")
    bars = _bars(closes)
    payload = run_backtest(base_spec(), bars, cfg(end_ms=T0 + (len(closes) - 1) * M15))
    for t in payload.trades:
        assert t.qty >= meta.min_qty
        assert (t.qty / meta.lot_step) == (t.qty / meta.lot_step).to_integral_value()
