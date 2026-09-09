"""Repositories: typed persistence operations (docs/persistence.md).

Conventions: callers pass an open Session; repos flush but never commit --
the service layer owns transaction boundaries (atomic run inserts depend on
it). Money crosses the boundary as Decimal and is stored as TEXT.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from alphalab_core.config import RunPayload
from alphalab_marketdata import BarRow

from . import models

USER = "local"


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return uuid.uuid4().hex


def money_str(value: Decimal) -> str:
    """Canonical money text: plain fixed notation, no exponent, no trailing dust."""
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return money_str(value)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


# --- strategies ---


def create_strategy(
    session: Session, *, name: str, spec_json: str, spec_hash: str,
    template_ref: dict[str, Any] | None, provenance: dict[str, Any],
) -> tuple[models.Strategy, models.StrategyVersion]:
    strategy = models.Strategy(
        id=new_id(), user_id=USER, name=name, template_ref=template_ref,
        current_version_id="", created_at=now_ms(), updated_at=now_ms(),
    )
    version = models.StrategyVersion(
        id=new_id(), strategy_id=strategy.id, version_number=1, spec=spec_json,
        spec_hash=spec_hash, parent_version_id=None, provenance=provenance, created_at=now_ms(),
    )
    strategy.current_version_id = version.id
    session.add(strategy)
    session.add(version)
    session.flush()
    return strategy, version


def add_strategy_version(
    session: Session, *, strategy_id: str, spec_json: str, spec_hash: str, provenance: dict[str, Any],
) -> models.StrategyVersion:
    strategy = session.get(models.Strategy, strategy_id)
    if strategy is None or strategy.user_id != USER:
        raise KeyError(f"strategy not found: {strategy_id}")
    latest = session.scalar(
        select(models.StrategyVersion)
        .where(models.StrategyVersion.strategy_id == strategy_id)
        .order_by(models.StrategyVersion.version_number.desc())
        .limit(1)
    )
    version = models.StrategyVersion(
        id=new_id(), strategy_id=strategy_id,
        version_number=(latest.version_number + 1 if latest else 1),
        spec=spec_json, spec_hash=spec_hash,
        parent_version_id=latest.id if latest else None,
        provenance=provenance, created_at=now_ms(),
    )
    strategy.current_version_id = version.id
    strategy.updated_at = now_ms()
    session.add(version)
    session.flush()
    return version


def get_strategy_version(session: Session, version_id: str) -> models.StrategyVersion | None:
    return session.get(models.StrategyVersion, version_id)


# --- datasets ---


def create_dataset(
    session: Session, *, symbol: str, timeframe: str, rows: list[BarRow],
    bars_hash: str, source: dict[str, Any], manifest: dict[str, Any],
) -> models.Dataset:
    dataset = models.Dataset(
        id=new_id(), user_id=USER, symbol=symbol, timeframe=timeframe, bar_count=len(rows),
        start_time=rows[0].open_time if rows else 0, end_time=rows[-1].open_time if rows else 0,
        bars_hash=bars_hash, source=source, manifest=manifest, created_at=now_ms(),
    )
    session.add(dataset)
    session.add_all(
        models.DatasetBar(dataset_id=dataset.id, open_time=r.open_time, o=r.open, h=r.high, l=r.low, c=r.close, v=r.volume)
        for r in rows
    )
    session.flush()
    return dataset


def get_dataset_by_hash(session: Session, bars_hash: str) -> models.Dataset | None:
    return session.scalar(select(models.Dataset).where(models.Dataset.bars_hash == bars_hash))


def get_dataset_bars(session: Session, dataset_id: str) -> list[BarRow]:
    rows = session.scalars(
        select(models.DatasetBar)
        .where(models.DatasetBar.dataset_id == dataset_id)
        .order_by(models.DatasetBar.open_time)
    ).all()
    return [BarRow(r.open_time, r.o, r.h, r.l, r.c, r.v) for r in rows]


# --- jobs ---


def create_job(session: Session) -> models.BacktestJob:
    job = models.BacktestJob(
        id=new_id(), state="queued", cancel_requested=0,
        progress={"barsProcessed": 0, "barTotal": 0}, created_at=now_ms(),
    )
    session.add(job)
    session.flush()
    return job


def set_job_running(session: Session, job_id: str, bar_total: int) -> None:
    job = session.get(models.BacktestJob, job_id)
    assert job is not None
    job.state = "running"
    job.started_at = now_ms()
    job.progress = {"barsProcessed": 0, "barTotal": bar_total}


def set_job_progress(session: Session, job_id: str, processed: int) -> None:
    job = session.get(models.BacktestJob, job_id)
    assert job is not None
    job.progress = {"barsProcessed": processed, "barTotal": job.progress.get("barTotal", 0)}


def finish_job(session: Session, job_id: str, state: str, error: str | None = None) -> None:
    assert state in ("completed", "failed", "cancelled")
    job = session.get(models.BacktestJob, job_id)
    assert job is not None
    job.state = state
    job.error = error
    job.finished_at = now_ms()


def request_cancel(session: Session, job_id: str) -> models.BacktestJob | None:
    job = session.get(models.BacktestJob, job_id)
    if job is None or job.state not in ("queued", "running"):
        return None
    job.cancel_requested = 1
    session.flush()
    return job


def recover_interrupted(session: Session) -> int:
    """Mark jobs stuck in running (process died) as failed. Returns count."""
    stuck = session.scalars(select(models.BacktestJob).where(models.BacktestJob.state == "running")).all()
    for job in stuck:
        job.state = "failed"
        job.error = "restarted: process did not survive the run"
        job.finished_at = now_ms()
    session.flush()
    return len(stuck)


# --- runs (atomic: run + trades + orders in one flush) ---


def downsample_equity(equity: list[tuple[int, Decimal]], limit: int = 2000) -> list[list[Any]]:
    if len(equity) <= limit:
        return [[t, money_str(e)] for t, e in equity]
    step = len(equity) / limit
    return [[equity[int(i * step)][0], money_str(equity[int(i * step)][1])] for i in range(limit)]


def full_resolution_hash(equity: list[tuple[int, Decimal]]) -> str:
    canonical = json.dumps([[t, money_str(e)] for t, e in equity], separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def insert_run(
    session: Session, *, job_id: str, strategy_version_id: str, dataset_id: str,
    spec_hash: str, dataset_hash: str, config_hash: str, result_hash: str,
    engine_version: str, config: dict[str, Any], metrics: dict[str, Any], payload: RunPayload, run_id: str | None = None,
) -> models.BacktestRun:
    run = models.BacktestRun(
        id=run_id or new_id(), job_id=job_id, strategy_version_id=strategy_version_id,
        dataset_id=dataset_id, spec_hash=spec_hash, dataset_hash=dataset_hash,
        config_hash=config_hash, result_hash=result_hash, engine_version=engine_version,
        config=json_safe(config), metrics=json_safe(metrics),
        equity_curve=downsample_equity(payload.equity),
        full_resolution_hash=full_resolution_hash(payload.equity),
        assumptions=list(payload.assumptions), warnings=dict(payload.warnings),
        created_at=now_ms(),
    )
    session.add(run)
    for t in payload.trades:
        session.add(models.Trade(
            id=new_id(), run_id=run.id, entry_bar=t.entry_bar, exit_bar=t.exit_bar,
            direction=t.direction, qty=money_str(t.qty), entry_price=money_str(t.entry_price),
            exit_price=money_str(t.exit_price), fees=money_str(t.fees),
            gross_pnl=money_str(t.gross_pnl), net_pnl=money_str(t.net_pnl),
            intended_risk=money_str(t.intended_risk), realized_risk=money_str(t.realized_risk),
            signal_time=t.signal_time,
            exit_reason=t.exit_reason, ambiguous=1 if t.ambiguous else 0,
        ))
    for o in payload.orders:
        session.add(models.Order(
            id=new_id(), run_id=run.id, signal_bar=o.signal_bar, fill_bar=o.fill_bar,
            kind="market", direction=o.direction,
            qty=money_str(o.qty) if o.fill_bar is not None else None, state=o.state,
            fill_price=money_str(o.fill_price) if o.fill_bar is not None else None,
            fees=money_str(o.fees) if o.fill_bar is not None else None,
        ))
    session.flush()
    return run


def get_run_by_result_hash(session: Session, result_hash: str) -> models.BacktestRun | None:
    return session.scalar(select(models.BacktestRun).where(models.BacktestRun.result_hash == result_hash))


def get_run(session: Session, run_id: str) -> models.BacktestRun | None:
    return session.get(models.BacktestRun, run_id)


# --- experiments ---


def create_experiment(
    session: Session, *, name: str, run_ids: list[str],
    baseline_run_id: str | None, hypothesis: str | None = None,
) -> models.Experiment:
    exp = models.Experiment(
        id=new_id(), user_id=USER, name=name, hypothesis=hypothesis,
        run_ids=list(run_ids), baseline_run_id=baseline_run_id, created_at=now_ms(),
    )
    session.add(exp)
    session.flush()
    return exp


def get_experiment(session: Session, experiment_id: str) -> models.Experiment | None:
    exp = session.get(models.Experiment, experiment_id)
    if exp is not None and exp.user_id != USER:
        return None
    return exp
