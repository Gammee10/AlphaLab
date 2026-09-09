"""Async job runner: asyncio orchestration, process-pool engine (docs/backtest-engine.md §10).

- Concurrency via semaphore; queue depth bounded (429 beyond).
- Engine runs in ProcessPoolExecutor; cancel/timeout/progress cross the
  boundary through the job row (worker.py).
- Timeout kills our wait, not the worker: completion writes are guarded by a
  fresh state read, so orphans can never persist.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from alphalab_contracts import result_hash
from alphalab_core.config import BacktestCancelled
from alphalab_core.engine import run_backtest
from alphalab_core.instruments import INSTRUMENT_META_VERSION
from alphalab_marketdata import TIMEFRAME_MS
from alphalab_store import models, repos
from alphalab_store.database import get_session_factory

from . import worker
from .service import (
    TooManyTrades,
    assemble_payload,
    finish_prepared_run,
    prepare_run,
    to_engine_config,
    window_arrays,
)
from .settings import Settings

log = logging.getLogger("alphalab.jobs")


def _public_error(exc: Exception) -> str:
    """Client-safe job error string.

    Typed domain errors keep their code + message; unknown failures are
    logged server-side (full traceback) and persist only a generic code,
    per docs/api.md ("500 internal, no stack to client").
    """
    from alphalab_contracts import AlphaLabError

    if isinstance(exc, AlphaLabError):
        return f"{exc.code}: {exc.message}"
    if isinstance(exc, TooManyTrades):
        return f"{exc.code}: {exc.message}"
    if isinstance(exc, KeyError):
        return f"NOT_FOUND: {exc}"
    log.exception("backtest job failed")
    return "INTERNAL: internal error"

_executor: ProcessPoolExecutor | None = None
_semaphore: asyncio.Semaphore | None = None


def _pool(settings: Settings) -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ProcessPoolExecutor(max_workers=settings.job_concurrency)
    return _executor


def _sem(settings: Settings) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.job_concurrency)
    return _semaphore


def queued_depth(settings: Settings) -> int:
    factory = get_session_factory(settings.db_path)
    with factory() as session:
        return int(
            session.scalar(
                select(func.count()).where(models.BacktestJob.state.in_(("queued", "running")))
            )
            or 0
        )


def task_payload(settings: Settings, prep: dict[str, Any], job_id: str) -> dict[str, Any]:
    cfg = prep["config_dict"]
    return {
        "db_path": str(settings.db_path),
        "job_id": job_id,
        "spec": prep["spec"],
        "rows": [[r.open_time, r.open, r.high, r.low, r.close, r.volume] for r in prep["rows"]],
        "symbol": prep["dataset"].symbol,
        "bar_step_ms": TIMEFRAME_MS[prep["dataset"].timeframe],
        "start_ms": cfg["startTime"],
        "end_ms": cfg["endTime"],
        "initial_capital": cfg["initialCapital"],
        "costs": {
            "spread_bps": str(prep["costs"].spread_bps),
            "slippage_bps": str(prep["costs"].slippage_bps),
            "commission_per_unit": str(prep["costs"].commission_per_unit),
        },
    }


def _dedupe_hash(prep: dict[str, Any], engine_version: str, raw_trades: list[dict[str, Any]]) -> str:
    from alphalab_core.config import Trade

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
        for t in raw_trades
    ]
    return result_hash(
        spec_hash=prep["spec_hash"], dataset_hash=prep["dataset_hash"],
        config_hash_=prep["config_hash"], engine_version=engine_version,
        instrument_meta_version=INSTRUMENT_META_VERSION, trades=trades,
    )


async def execute_async(
    settings: Settings, job_id: str, strategy_version_id: str, dataset_id: str, request: dict[str, Any]
) -> None:
    factory = get_session_factory(settings.db_path)
    async with _sem(settings):
        with factory() as session:
            try:
                prep = prepare_run(
                    session, strategy_version_id=strategy_version_id, dataset_id=dataset_id, request=request
                )
            except Exception as exc:  # validation etc: terminal failure, never retried silently
                repos.finish_job(session, job_id, "failed", _public_error(exc))
                session.commit()
                return
            repos.set_job_running(session, job_id, prep["bar_count"])
            session.commit()
        loop = asyncio.get_running_loop()
        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(_pool(settings), worker.run_engine_task, task_payload(settings, prep, job_id)),
                timeout=settings.job_timeout_s,
            )
        except BacktestCancelled:
            with factory() as session:
                repos.finish_job(session, job_id, "cancelled")
                session.commit()
            return
        except (asyncio.TimeoutError, TimeoutError):
            with factory() as session:
                repos.finish_job(session, job_id, "failed", "timeout: run exceeded 120s")
                session.commit()
            return
        except Exception as exc:
            with factory() as session:
                repos.finish_job(session, job_id, "failed", _public_error(exc))
                session.commit()
            return
        with factory() as session:
            job = session.get(models.BacktestJob, job_id)
            if job is None or job.state != "running" or job.cancel_requested:
                repos.finish_job(
                    session, job_id,
                    "cancelled" if job is not None and job.cancel_requested else "failed",
                    "cancelled before persist" if job is not None and job.cancel_requested else "superseded",
                )
                session.commit()
                return
            try:
                payload = assemble_payload(raw)
                run, _ = finish_prepared_run(
                    session, prep=prep, payload=payload, job_id=job_id, max_trades=settings.max_trades_per_run
                )
                repos.finish_job(session, job_id, "completed")
                job.progress = {"barsProcessed": prep["bar_count"], "barTotal": prep["bar_count"], "runId": run.id}
                session.commit()
            except IntegrityError:
                # Lost the idempotency race: return the winner (docs/api.md).
                session.rollback()
                rh = _dedupe_hash(prep, raw["engine_version"], raw["trades"])
                with factory() as session2:
                    existing = repos.get_run_by_result_hash(session2, rh)
                    repos.finish_job(session2, job_id, "completed")
                    j = session2.get(models.BacktestJob, job_id)
                    if j is not None and existing is not None:
                        j.progress = {"barsProcessed": prep["bar_count"], "barTotal": prep["bar_count"],
                                      "runId": existing.id, "deduped": True}
                    session2.commit()
            except Exception as exc:
                session.rollback()
                with factory() as session3:
                    repos.finish_job(session3, job_id, "failed", _public_error(exc))
                    session3.commit()


def _fail_sync_job(settings: Settings, job_id: str, exc: Exception) -> None:
    factory = get_session_factory(settings.db_path)
    with factory() as session:
        repos.finish_job(session, job_id, "failed", _public_error(exc))
        session.commit()


def execute_sync(
    settings: Settings, strategy_version_id: str, dataset_id: str, request: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Inline path (<200k bars). Returns (run_json, deduped). Raises on failure.

    The job row is always terminal on return-or-raise, so failures can never
    orphan a ``queued`` row and inflate queue depth.
    """
    factory = get_session_factory(settings.db_path)
    with factory() as session:
        prep = prepare_run(session, strategy_version_id=strategy_version_id, dataset_id=dataset_id, request=request)
        job = repos.create_job(session)
        repos.set_job_running(session, job.id, prep["bar_count"])
        session.commit()
        job_id = job.id
    try:
        payload = run_backtest(prep["spec"], window_arrays(prep), to_engine_config(prep))
    except Exception as exc:
        _fail_sync_job(settings, job_id, exc)
        raise
    with factory() as session:
        try:
            run, deduped = finish_prepared_run(
                session, prep=prep, payload=payload, job_id=job_id, max_trades=settings.max_trades_per_run
            )
        except IntegrityError:
            # Concurrent identical submission won the race; return the winner.
            from .worker import trade_to_dict

            session.rollback()
            rh = _dedupe_hash(prep, payload.engine_version, [trade_to_dict(t) for t in payload.trades])
            with factory() as session2:
                existing = repos.get_run_by_result_hash(session2, rh)
                assert existing is not None
                repos.finish_job(session2, job_id, "completed")
                session2.commit()
                return run_to_json(session2, existing.id), True
        except Exception as exc:
            session.rollback()
            _fail_sync_job(settings, job_id, exc)
            raise
        repos.finish_job(session, job_id, "completed")
        session.commit()
        return run_to_json(session, run.id), deduped


def run_to_json(session: Any, run_id: str) -> dict[str, Any]:
    run = session.get(models.BacktestRun, run_id)
    assert run is not None
    return {
        "id": run.id, "jobId": run.job_id, "strategyVersionId": run.strategy_version_id,
        "datasetId": run.dataset_id, "specHash": run.spec_hash, "datasetHash": run.dataset_hash,
        "configHash": run.config_hash, "resultHash": run.result_hash,
        "engineVersion": run.engine_version, "config": run.config, "metrics": run.metrics,
        "equityCurve": run.equity_curve, "fullResolutionHash": run.full_resolution_hash,
        "assumptions": run.assumptions, "warnings": run.warnings, "createdAt": run.created_at,
    }
