"""Run identity hashing (docs/results-experiments.md, hash scope).

resultHash = sha256(specHash + datasetHash + configHash + engineVersion
  + instrumentMetaVersion + canonicalTrades)
"""

from __future__ import annotations

from typing import Any

from alphalab_core.config import Trade

from .canonical import content_hash


def config_hash(config: dict[str, Any]) -> str:
    return content_hash(config)


def _trade_dict(t: Trade) -> dict[str, Any]:
    return {
        "entry_bar": t.entry_bar,
        "entry_time": t.entry_time,
        "exit_bar": t.exit_bar,
        "exit_time": t.exit_time,
        "signal_bar": t.signal_bar,
        "signal_time": t.signal_time,
        "direction": t.direction,
        "qty": t.qty,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "fees": t.fees,
        "gross_pnl": t.gross_pnl,
        "net_pnl": t.net_pnl,
        "intended_risk": t.intended_risk,
        "realized_risk": t.realized_risk,
        "exit_reason": t.exit_reason,
        "ambiguous": t.ambiguous,
    }


def result_hash(
    *,
    spec_hash: str,
    dataset_hash: str,
    config_hash_: str,
    engine_version: str,
    instrument_meta_version: str,
    trades: list[Trade],
) -> str:
    canonical_trades = sorted(
        (_trade_dict(t) for t in trades),
        key=lambda d: (d["entry_bar"], d["exit_bar"], d["direction"]),
    )
    return content_hash(
        {
            "specHash": spec_hash,
            "datasetHash": dataset_hash,
            "configHash": config_hash_,
            "engineVersion": engine_version,
            "instrumentMetaVersion": instrument_meta_version,
            "trades": canonical_trades,
        }
    )
