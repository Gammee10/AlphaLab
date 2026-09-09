"""Worker entry points for process-pool backtest execution.

Everything here must be importable and picklable under multiprocessing spawn:
module-level functions, plain-data arguments, no closures, no shared state.
Cancel/progress cross the process boundary through the SQLite job row.
"""

from __future__ import annotations

import sqlite3
import sys
from functools import partial
from pathlib import Path
from typing import Any

# Spawned children inherit sys.path on most platforms, but be explicit: the
# backend package lives next to this file's parent.
_BACKEND = str(Path(__file__).resolve().parent.parent)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def check_cancelled(db_path: str, job_id: str, bar: int) -> bool:
    del bar  # signature fixed for the engine hook; polling is coarse by design
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        row = conn.execute(
            "SELECT state, cancel_requested FROM backtest_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return True
    state, cancel_requested = row
    return bool(cancel_requested) or state in ("cancelled", "failed")


def report_progress(db_path: str, job_id: str, processed: int, total: int) -> None:
    import json

    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute(
            "UPDATE backtest_jobs SET progress = ? WHERE id = ?",
            (json.dumps({"barsProcessed": processed, "barTotal": total}), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def run_engine_task(task: dict[str, Any]) -> dict[str, Any]:
    """Execute one backtest in a worker process. Returns JSON-safe payload parts."""
    from decimal import Decimal

    from alphalab_core.bars import BarArrays
    from alphalab_core.config import BacktestConfig, Costs
    from alphalab_core.engine import run_backtest
    from alphalab_marketdata import BarRow, to_bar_arrays

    db_path = task["db_path"]
    job_id = task["job_id"]
    rows = [BarRow(*r) for r in task["rows"]]
    bars: BarArrays = to_bar_arrays(rows)
    costs = Costs(
        spread_bps=Decimal(task["costs"]["spread_bps"]),
        slippage_bps=Decimal(task["costs"]["slippage_bps"]),
        commission_per_unit=Decimal(task["costs"]["commission_per_unit"]),
    )
    config = BacktestConfig(
        symbol=task["symbol"], bar_step_ms=task["bar_step_ms"], start_ms=task["start_ms"],
        end_ms=task["end_ms"], initial_capital=task["initial_capital"], costs=costs,
    )
    payload = run_backtest(
        task["spec"], bars, config,
        should_cancel=partial(check_cancelled, db_path, job_id),
        progress=partial(report_progress, db_path, job_id),
    )
    return {
        "trades": [trade_to_dict(t) for t in payload.trades],
        "orders": [order_to_dict(o) for o in payload.orders],
        "equity": [[t, str(e)] for t, e in payload.equity],
        "warnings": payload.warnings,
        "assumptions": payload.assumptions,
        "engine_version": payload.engine_version,
    }


def trade_to_dict(t: Any) -> dict[str, Any]:
    return {
        "entry_bar": t.entry_bar, "entry_time": t.entry_time,
        "exit_bar": t.exit_bar, "exit_time": t.exit_time,
        "signal_bar": t.signal_bar, "signal_time": t.signal_time,
        "direction": t.direction, "qty": str(t.qty),
        "entry_price": str(t.entry_price), "exit_price": str(t.exit_price),
        "fees": str(t.fees), "gross_pnl": str(t.gross_pnl), "net_pnl": str(t.net_pnl),
        "intended_risk": str(t.intended_risk), "realized_risk": str(t.realized_risk),
        "exit_reason": t.exit_reason, "ambiguous": t.ambiguous,
    }


def order_to_dict(o: Any) -> dict[str, Any]:
    return {
        "signal_bar": o.signal_bar, "signal_time": o.signal_time,
        "direction": o.direction, "state": o.state, "fill_bar": o.fill_bar,
        "fill_time": o.fill_time,
        "qty": str(o.qty) if o.qty is not None else None,
        "fill_price": str(o.fill_price) if o.fill_price is not None else None,
        "fees": str(o.fees) if o.fees is not None else None,
    }
