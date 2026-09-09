"""Diagnose template-default tradeability on the bundled EURUSD sample."""
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alphalab_core.bars import BarArrays
from alphalab_core.config import BacktestConfig, Costs
from alphalab_core.engine import run_backtest
from alphalab_core.templates import TEMPLATES, instantiate
from alphalab_marketdata import import_csv, to_bar_arrays


def load():
    text = open("data/samples/eurusd_m15.csv", encoding="utf-8").read()
    rows, _ = import_csv(text, "EURUSD", "M15")
    return to_bar_arrays(rows), rows[0].open_time, rows[-1].open_time


bars, t0, t1 = load()
for tid in TEMPLATES:
    for risk, mult in (("0.5", 3), ("0.5", 5), ("0.25", 3), ("1.0", 5)):
        spec = instantiate(tid, {"riskPct": float(risk)})
        spec["risk"]["maxNotionalMult"] = mult
        cfg = BacktestConfig(symbol="EURUSD", bar_step_ms=900_000, start_ms=t0, end_ms=t1,
                             initial_capital=Decimal("10000"),
                             costs=Costs(spread_bps=Decimal("15"), slippage_bps=Decimal("5"),
                                         commission_per_unit=Decimal("0")))
        p = run_backtest(spec, bars, cfg)
        w = p.warnings
        print(f"{tid:26s} risk={risk}% mult={mult}x -> trades={len(p.trades):4d} "
              f"capitalSkips={w['capitalSkips']:3d} warmup={w['warmupBarsSkipped']:3d} "
              f"ambiguous={w['ambiguousBars']}")
