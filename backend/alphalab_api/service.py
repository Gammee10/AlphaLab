"""Backtest orchestration: validate -> slice -> execute -> measure -> persist.

Single choke point for both sync and async paths so the two can never diverge
in semantics (docs/api.md, docs/backtest-engine.md).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from alphalab_contracts import (
    check_run_compatibility,
    config_hash,
    result_hash,
    spec_hash,
    validate_spec_or_raise,
)
from alphalab_core.bars import BarArrays
from alphalab_core.config import ENGINE_VERSION, BacktestConfig, Costs, RunPayload
from alphalab_core.engine import run_backtest
from alphalab_core.instruments import INSTRUMENT_META_VERSION
from alphalab_core.metrics import compute_metrics
from alphalab_marketdata import BarRow, has_volume, select_range, to_bar_arrays
from alphalab_marketdata import TIMEFRAME_MS
from alphalab_store import models, repos

from .settings import Settings

COST_PRESETS = {"EURUSD": "15", "GBPUSD": "20", "XAUUSD": "25", "BTCUSD": "5"}
DEFAULT_SLIPPAGE_BPS = "5"


class TooManyTrades(Exception):
    code = "TOO_MANY_TRADES"

    def __init__(self, count: int) -> None:
        super().__init__(f"{count} trades exceed the 50,000/run cap; widen stops or use a longer timeframe")
        self.message = str(self)
        self.count = count


def spec_max_period(spec: dict[str, Any]) -> int:
    best = 1
    for ind in spec.get("indicators", []):
        kind = ind.get("kind")
        for key in ("period", "slow"):
            if isinstance(ind.get(key), (int, float)):
                best = max(best, int(ind[key]))
    return best


def warmup_bars(spec: dict[str, Any]) -> int:
    return max(3 * spec_max_period(spec), 50)


def build_costs(symbol: str, raw: dict[str, Any] | None) -> Costs:
    raw = raw or {}
    return Costs(
        spread_bps=Decimal(str(raw.get("spreadBps", COST_PRESETS.get(symbol, "15")))),
        slippage_bps=Decimal(str(raw.get("slippageBps", DEFAULT_SLIPPAGE_BPS))),
        commission_per_unit=Decimal(str(raw.get("commissionPerUnit", "0"))),
    )


def build_config_dict(
    *, symbol: str, timeframe: str, start_ms: int, end_ms: int, initial_capital: str,
    costs: Costs, in_sample: Any, out_of_sample: Any,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "startTime": start_ms,
        "endTime": end_ms,
        "initialCapital": initial_capital,
        "costs": {
            "spreadBps": str(costs.spread_bps),
            "slippageBps": str(costs.slippage_bps),
            "commissionPerUnit": str(costs.commission_per_unit),
        },
        "inSample": in_sample,
        "outOfSample": out_of_sample,
        "instrumentMetaVersion": INSTRUMENT_META_VERSION,
        "engineVersion": ENGINE_VERSION,
    }


def prepare_run(
    session: Session, *, strategy_version_id: str, dataset_id: str, request: dict[str, Any],
) -> dict[str, Any]:
    """Validate + slice everything the engine needs. No execution, no writes."""
    version = repos.get_strategy_version(session, strategy_version_id)
    if version is None:
        raise KeyError(f"strategy version not found: {strategy_version_id}")
    spec = json.loads(version.spec)
    validate_spec_or_raise(spec)
    dataset = session.get(models.Dataset, dataset_id)
    if dataset is None:
        raise KeyError(f"dataset not found: {dataset_id}")
    rows = repos.get_dataset_bars(session, dataset_id)
    compat = check_run_compatibility(spec, has_volume=has_volume(rows))
    if compat:
        from alphalab_contracts import DatasetInvalidError

        raise DatasetInvalidError(f"{compat[0].path}: {compat[0].message}")
    start_ms = int(request["startTime"])
    end_ms = int(request["endTime"])
    if start_ms >= end_ms:
        from alphalab_contracts import StrategyInvalidError, ValidationIssue

        raise StrategyInvalidError([ValidationIssue("config", "VALIDATION_ERROR", "startTime must precede endTime")])
    window, cold_start, deficit = select_range(rows, start_ms, end_ms, warmup_bars(spec))
    costs = build_costs(dataset.symbol, request.get("costs"))
    config_dict = build_config_dict(
        symbol=dataset.symbol, timeframe=dataset.timeframe, start_ms=start_ms, end_ms=end_ms,
        initial_capital=str(request.get("initialCapital", "10000")), costs=costs,
        in_sample=request.get("inSample"), out_of_sample=request.get("outOfSample"),
    )
    in_window = [r for r in window if start_ms <= r.open_time <= end_ms]
    return {
        "spec": spec,
        "version": version,
        "dataset": dataset,
        "rows": window,
        "cold_start": cold_start,
        "cold_deficit": deficit,
        "costs": costs,
        "config_dict": config_dict,
        "bar_count": len(in_window),
        "spec_hash": version.spec_hash,
        "dataset_hash": dataset.bars_hash,
        "config_hash": config_hash(config_dict),
    }


def to_engine_config(prep: dict[str, Any]) -> BacktestConfig:
    dataset = prep["dataset"]
    cfg = prep["config_dict"]
    return BacktestConfig(
        symbol=dataset.symbol,
        bar_step_ms=TIMEFRAME_MS[dataset.timeframe],
        start_ms=cfg["startTime"],
        end_ms=cfg["endTime"],
        initial_capital=Decimal(cfg["initialCapital"]),
        costs=prep["costs"],
    )


def window_arrays(prep: dict[str, Any]) -> BarArrays:
    return to_bar_arrays(prep["rows"])


def assemble_payload(raw: dict[str, Any]) -> RunPayload:
    """Rebuild a RunPayload from worker-JSON (async path) for shared finishing."""
    from alphalab_core.config import Order, Trade

    trades = [
        Trade(
            entry_bar=t["entry_bar"], entry_time=t["entry_time"], exit_bar=t["exit_bar"],
            exit_time=t["exit_time"], signal_bar=t["signal_bar"], signal_time=t["signal_time"],
            direction=t["direction"], qty=Decimal(t["qty"]), entry_price=Decimal(t["entry_price"]),
            exit_price=Decimal(t["exit_price"]), fees=Decimal(t["fees"]),
            gross_pnl=Decimal(t["gross_pnl"]), net_pnl=Decimal(t["net_pnl"]),
            intended_risk=Decimal(t["intended_risk"]), realized_risk=Decimal(t["realized_risk"]),
            exit_reason=t["exit_reason"], ambiguous=bool(t["ambiguous"]),
        )
        for t in raw["trades"]
    ]
    orders = [
        Order(
            signal_bar=o["signal_bar"], signal_time=o["signal_time"], direction=o["direction"],
            state=o["state"], fill_bar=o["fill_bar"], fill_time=o["fill_time"],
            qty=Decimal(o["qty"]) if o["qty"] is not None else Decimal("0"),
            fill_price=Decimal(o["fill_price"]) if o["fill_price"] is not None else Decimal("0"),
            fees=Decimal(o["fees"]) if o["fees"] is not None else Decimal("0"),
        )
        for o in raw["orders"]
    ]
    return RunPayload(
        trades=trades, orders=orders,
        equity=[(t, Decimal(e)) for t, e in raw["equity"]],
        warnings=dict(raw["warnings"]), assumptions=list(raw["assumptions"]),
        engine_version=raw["engine_version"],
    )


def finish_prepared_run(
    session: Session, *, prep: dict[str, Any], payload: RunPayload, job_id: str,
    max_trades: int,
) -> tuple[models.BacktestRun, bool]:
    """Measure, dedupe-check, and atomically persist. Returns (run, deduped)."""
    if len(payload.trades) > max_trades:
        raise TooManyTrades(len(payload.trades))
    if prep["cold_start"]:
        payload.warnings["coldStart"] = True
        payload.warnings["coldStartDeficit"] = prep["cold_deficit"]
    rh = result_hash(
        spec_hash=prep["spec_hash"], dataset_hash=prep["dataset_hash"],
        config_hash_=prep["config_hash"], engine_version=payload.engine_version,
        instrument_meta_version=INSTRUMENT_META_VERSION, trades=payload.trades,
    )
    existing = repos.get_run_by_result_hash(session, rh)
    if existing is not None:
        return existing, True
    metrics = compute_metrics(
        payload.trades, payload.equity, Decimal(prep["config_dict"]["initialCapital"]),
        prep["dataset"].timeframe,
    )
    run = repos.insert_run(
        session, job_id=job_id, strategy_version_id=prep["version"].id,
        dataset_id=prep["dataset"].id, spec_hash=prep["spec_hash"],
        dataset_hash=prep["dataset_hash"], config_hash=prep["config_hash"],
        result_hash=rh, engine_version=payload.engine_version,
        config=prep["config_dict"], metrics=metrics, payload=payload,
    )
    return run, False
