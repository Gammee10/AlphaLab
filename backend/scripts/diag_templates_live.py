"""Verify every template trades out-of-the-box on the bundled sample."""
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alphalab_core.config import BacktestConfig, Costs
from alphalab_core.engine import run_backtest
from alphalab_core.templates import TEMPLATES, instantiate
from alphalab_marketdata import import_csv, to_bar_arrays

text = open("data/samples/eurusd_m15.csv", encoding="utf-8").read()
rows, _ = import_csv(text, "EURUSD", "M15")
bars = to_bar_arrays(rows)
for tid in TEMPLATES:
    spec = instantiate(tid, {})
    cfg = BacktestConfig(
        symbol="EURUSD", bar_step_ms=900_000, start_ms=rows[0].open_time, end_ms=rows[-1].open_time,
        initial_capital=Decimal("10000"),
        costs=Costs(spread_bps=Decimal("15"), slippage_bps=Decimal("5"), commission_per_unit=Decimal("0")),
    )
    p = run_backtest(spec, bars, cfg)
    w = p.warnings
    net = sum((t.net_pnl for t in p.trades), Decimal(0))
    print(tid, "DEFAULTS -> trades=", len(p.trades), "net=", net,
          "capitalSkips=", w["capitalSkips"], "ambiguous=", w["ambiguousBars"])
