"""Run identity: determinism hash, sensitivity, config hashing."""

from __future__ import annotations

from decimal import Decimal

from alphalab_contracts import config_hash, result_hash, spec_hash
from alphalab_core.config import BacktestConfig, Costs
from alphalab_core.engine import run_backtest
from alphalab_core.instruments import INSTRUMENT_META_VERSION

from helpers import M15, T0, basic_bars, base_spec, cfg


def _run(slippage: str = "0"):
    spec = base_spec()
    base = cfg(end_ms=T0 + 4 * M15)
    config = BacktestConfig(
        symbol=base.symbol, bar_step_ms=base.bar_step_ms, start_ms=base.start_ms,
        end_ms=base.end_ms, initial_capital=base.initial_capital,
        costs=Costs(slippage_bps=Decimal(slippage)),
    )
    return spec, config, run_backtest(spec, basic_bars(), config)


def _hashes(spec, config, payload, dataset_hash="d" * 64):
    sh = spec_hash(spec)
    ch = config_hash(
        {"symbol": config.symbol, "start": config.start_ms, "end": config.end_ms,
         "capital": str(config.initial_capital), "costs": str(config.costs.slippage_bps)}
    )
    rh = result_hash(
        spec_hash=sh, dataset_hash=dataset_hash, config_hash_=ch,
        engine_version=payload.engine_version,
        instrument_meta_version=INSTRUMENT_META_VERSION, trades=payload.trades,
    )
    return sh, ch, rh


def test_determinism_identical_hash() -> None:
    spec, config, p1 = _run()
    _, _, p2 = _run()
    assert _hashes(spec, config, p1) == _hashes(spec, config, p2)


def test_sensitivity_changes_hash() -> None:
    spec, config, p1 = _run("0")
    _, _, p3 = _run("5")
    assert _hashes(spec, config, p1)[2] != _hashes(spec, config, p3)[2]


def test_config_hash_stable_and_sensitive() -> None:
    a = {"spread": 15, "capital": 10000}
    assert config_hash(a) == config_hash(dict(a))
    assert config_hash(a) != config_hash({"spread": 20, "capital": 10000})
