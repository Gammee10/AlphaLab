"""Backtest, job, trade, and experiment routes (docs/api.md)."""

from __future__ import annotations

import asyncio
import itertools
import json
import threading
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from alphalab_store import models, repos

from . import jobs as job_runner
from .deps import session_of, settings_of
from .service import prepare_run

router = APIRouter(prefix="/api")

# Serializes queue admission (depth check + job insert) so concurrent
# bursts cannot both pass the check and overfill the queue.
_admission_lock = threading.Lock()


class BacktestRequest(BaseModel):
    strategyVersionId: str
    datasetId: str
    config: dict[str, Any]


_MAX_CAPITAL = "1000000000000"  # 1e12 sanity cap
_MAX_BPS = "100000"  # 1000% sanity cap on spread/slippage
_MAX_COMMISSION = "1000000000"


def _as_ms(value: Any, path: str) -> int:
    from alphalab_contracts import ValidationError

    if isinstance(value, bool):
        raise ValidationError(f"config.{path} must be an integer UTC-ms timestamp")
    if isinstance(value, int):
        ms = value
    elif isinstance(value, str) and value.strip().lstrip("+-").isdigit():
        ms = int(value.strip())
    else:
        raise ValidationError(f"config.{path} must be an integer UTC-ms timestamp")
    if not 0 < ms < 2**63:
        raise ValidationError(f"config.{path} is out of range")
    return ms


def _as_decimal(value: Any, path: str, minimum: str, maximum: str, *, allow_zero: bool) -> Any:
    from decimal import Decimal, InvalidOperation

    from alphalab_contracts import ValidationError

    if isinstance(value, bool):
        raise ValidationError(f"config.{path} must be numeric")
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise ValidationError(f"config.{path} must be numeric") from None
    if d.is_nan() or not d.is_finite():
        raise ValidationError(f"config.{path} must be finite")
    lo, hi = Decimal(minimum), Decimal(maximum)
    if d < lo or d > hi or (d == 0 and not allow_zero):
        raise ValidationError(f"config.{path} must be in [{minimum}, {maximum}]"
                              + ("" if allow_zero else ", non-zero"))
    return d


def _request_dict_from_config(config: Any) -> dict[str, Any]:
    """Validate raw run-config input; raises ValidationError (400), never 500."""
    from alphalab_contracts import ValidationError

    if not isinstance(config, dict):
        raise ValidationError("config must be an object")
    for key in ("startTime", "endTime"):
        if config.get(key) is None:
            raise ValidationError(f"config.{key} is required")
    costs = config.get("costs")
    if costs is None:
        costs = {}
    if not isinstance(costs, dict):
        raise ValidationError("config.costs must be an object")
    for key, maximum in (("spreadBps", _MAX_BPS), ("slippageBps", _MAX_BPS),
                         ("commissionPerUnit", _MAX_COMMISSION)):
        if costs.get(key) is not None:
            _as_decimal(costs[key], f"costs.{key}", "0", maximum, allow_zero=True)
    return {
        "startTime": _as_ms(config.get("startTime"), "startTime"),
        "endTime": _as_ms(config.get("endTime"), "endTime"),
        "initialCapital": str(_as_decimal(
            config.get("initialCapital", "10000"), "initialCapital", "0", _MAX_CAPITAL,
            allow_zero=False)),
        "costs": costs,
        "inSample": config.get("inSample"),
        "outOfSample": config.get("outOfSample"),
    }


def _request_dict(body: BacktestRequest) -> dict[str, Any]:
    return _request_dict_from_config(body.config)


@router.post("/backtests")
def create_backtest(body: BacktestRequest, request: Request) -> JSONResponse:
    settings = settings_of(request)
    req = _request_dict(body)
    with session_of(request) as session:
        prep = prepare_run(session, strategy_version_id=body.strategyVersionId,
                           dataset_id=body.datasetId, request=req)
        bar_count = prep["bar_count"]
    if bar_count < settings.sync_bar_threshold:
        with _admission_lock:
            if job_runner.queued_depth(settings) >= settings.job_queue_limit:
                return JSONResponse({"code": "RATE_LIMITED", "message": "job queue full",
                                     "details": {}}, 429)
        run_json, deduped = job_runner.execute_sync(settings, body.strategyVersionId, body.datasetId, req)
        run_json["deduped"] = deduped
        return JSONResponse({"run": run_json}, 200)
    with _admission_lock:
        if job_runner.queued_depth(settings) >= settings.job_queue_limit:
            return JSONResponse({"code": "RATE_LIMITED", "message": "job queue full", "details": {}}, 429)
        with session_of(request) as session:
            job = repos.create_job(session)
            session.commit()
            job_id, progress = job.id, dict(job.progress)
    asyncio.create_task(job_runner.execute_async(
        settings, job_id, body.strategyVersionId, body.datasetId, req))
    return JSONResponse({"job": {"id": job_id, **progress, "state": "queued"}}, 202)


def _trade_json(run_id: str, t: models.Trade, index: int) -> dict[str, Any]:
    return {
        "id": f"{run_id}:{index}", "entryBar": t.entry_bar, "exitBar": t.exit_bar,
        "entryTime": t.entry_time, "exitTime": t.exit_time,
        "direction": t.direction, "qty": t.qty, "entryPrice": t.entry_price,
        "exitPrice": t.exit_price, "fees": t.fees, "grossPnl": t.gross_pnl,
        "netPnl": t.net_pnl, "exitReason": t.exit_reason, "ambiguous": bool(t.ambiguous),
    }


@router.get("/backtests")
def list_backtests(request: Request, limit: int = 20) -> dict[str, Any]:
    from sqlalchemy import select

    capped = max(1, min(limit, 100))
    with session_of(request) as session:
        runs = session.scalars(
            select(models.BacktestRun).order_by(models.BacktestRun.created_at.desc()).limit(capped)
        ).all()
        return {"runs": [
            {"id": r.id, "resultHash": r.result_hash, "strategyVersionId": r.strategy_version_id,
             "datasetId": r.dataset_id, "engineVersion": r.engine_version,
             "tradeCount": r.metrics.get("tradeCount"), "netProfit": r.metrics.get("netProfit"),
             "winRate": r.metrics.get("winRate"), "profitFactor": r.metrics.get("profitFactor"),
             "maxDrawdownPct": r.metrics.get("maxDrawdownPct"), "createdAt": r.created_at}
            for r in runs
        ]}


@router.get("/backtests/{run_id}")
def get_backtest(run_id: str, request: Request) -> dict[str, Any]:
    with session_of(request) as session:
        run = repos.get_run(session, run_id)
        if run is None:
            raise KeyError(f"run not found: {run_id}")
        trades = session.scalars(
            select(models.Trade).where(models.Trade.run_id == run_id).order_by(models.Trade.exit_bar)
        ).all()
        payload: dict[str, Any] = dict(job_runner.run_to_json(session, run_id))
        if len(trades) <= 5000:
            payload["trades"] = [_trade_json(run_id, t, i) for i, t in enumerate(trades)]
        else:
            payload["trades"] = {"total": len(trades), "page": 0, "pageSize": 100,
                                 "url": f"/api/backtests/{run_id}/trades?page=0"}
        return {"run": payload}


@router.get("/backtests/{run_id}/trades")
def get_trades(run_id: str, request: Request, page: int = 0, pageSize: int = 100) -> dict[str, Any]:
    page_size = max(1, min(pageSize, 1000))
    with session_of(request) as session:
        if repos.get_run(session, run_id) is None:
            raise KeyError(f"run not found: {run_id}")
        trades = session.scalars(
            select(models.Trade).where(models.Trade.run_id == run_id).order_by(models.Trade.exit_bar)
        ).all()
        start = page * page_size
        return {
            "trades": [_trade_json(run_id, t, start + i) for i, t in enumerate(trades[start:start + page_size])],
            "total": len(trades), "page": page, "pageSize": page_size,
        }


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    with session_of(request) as session:
        job = session.get(models.BacktestJob, job_id)
        if job is None:
            raise KeyError(f"job not found: {job_id}")
        return {"job": {"id": job.id, "state": job.state, "progress": job.progress,
                        "error": job.error, "createdAt": job.created_at,
                        "startedAt": job.started_at, "finishedAt": job.finished_at}}


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str, request: Request) -> JSONResponse:
    with session_of(request) as session:
        job = repos.request_cancel(session, job_id)
        if job is None:
            existing = session.get(models.BacktestJob, job_id)
            if existing is None:
                return JSONResponse({"code": "NOT_FOUND", "message": f"job not found: {job_id}", "details": {}}, 404)
            return JSONResponse(
                {"code": "JOB_NOT_CANCELLABLE", "message": f"job is {existing.state}", "details": {}}, 409)
        session.commit()
        return JSONResponse({"job": {"id": job.id, "state": job.state, "cancelRequested": True}})


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    settings = settings_of(request)

    async def stream() -> AsyncIterator[str]:
        while True:
            if await request.is_disconnected():
                break
            with session_of(request) as session:
                job = session.get(models.BacktestJob, job_id)
                if job is None:
                    yield 'event: error\ndata: {"code":"NOT_FOUND"}\n\n'
                    break
                yield f"data: {json.dumps({'state': job.state, 'progress': job.progress, 'error': job.error})}\n\n"
                if job.state in ("completed", "failed", "cancelled"):
                    break
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


class CreateExperiment(BaseModel):
    name: str
    runIds: list[str]
    baselineRunId: str | None = None
    hypothesis: str | None = None


def _diff_paths(a: Any, b: Any, prefix: str = "", limit: int = 50) -> list[str]:
    out: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if len(out) >= limit:
                break
            if key not in a:
                out.append(f"{prefix}{key} (added)")
            elif key not in b:
                out.append(f"{prefix}{key} (removed)")
            elif a[key] != b[key]:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    out.extend(_diff_paths(a[key], b[key], f"{prefix}{key}.", limit - len(out)))
                else:
                    out.append(f"{prefix}{key}: {a[key]!r} -> {b[key]!r}")
    elif a != b and prefix:
        out.append(f"{prefix.rstrip('.')}: {a!r} -> {b!r}")
    return out


@router.post("/experiments", status_code=201)
def create_experiment(body: CreateExperiment, request: Request) -> dict[str, Any]:
    if not 2 <= len(body.runIds) <= 32:
        from alphalab_contracts import ValidationError

        raise ValidationError("experiments group 2..32 runs")
    with session_of(request) as session:
        for rid in itertools.chain(body.runIds, [body.baselineRunId] if body.baselineRunId else []):
            if repos.get_run(session, rid) is None:
                raise KeyError(f"run not found: {rid}")
        exp = repos.create_experiment(session, name=body.name, run_ids=body.runIds,
                                      baseline_run_id=body.baselineRunId, hypothesis=body.hypothesis)
        session.commit()
        return {"experiment": {"id": exp.id, "name": exp.name}}


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, request: Request) -> dict[str, Any]:
    with session_of(request) as session:
        exp = repos.get_experiment(session, experiment_id)
        if exp is None:
            raise KeyError(f"experiment not found: {experiment_id}")
        runs: list[models.BacktestRun] = [
            r for r in (repos.get_run(session, rid) for rid in exp.run_ids) if r is not None
        ]
        spec_of = {}
        for r in runs:
            v = repos.get_strategy_version(session, r.strategy_version_id)
            spec_of[r.id] = json.loads(v.spec) if v is not None else {}
        summaries = [
            {"id": r.id, "resultHash": r.result_hash, "metrics": r.metrics,
             "specHash": r.spec_hash, "config": r.config} for r in runs
        ]
        diff: list[str] = []
        deltas: dict[str, Any] = {}
        baseline = next((r for r in runs if r.id == exp.baseline_run_id), runs[0] if runs else None)
        if baseline is not None:
            for r in runs:
                if r.id == baseline.id:
                    continue
                changed = _diff_paths({"config": baseline.config}, {"config": r.config})
                changed += _diff_paths({"spec": spec_of.get(baseline.id, {})}, {"spec": spec_of.get(r.id, {})})
                diff.append(f"{r.id} vs baseline: " + ("; ".join(changed) if changed else "identical config+spec"))
            base_metrics = baseline.metrics
            for r in runs:
                if r.id == baseline.id:
                    continue
                deltas[r.id] = {
                    k: _delta(base_metrics.get(k), r.metrics.get(k))
                    for k in ("netProfit", "profitFactor", "maxDrawdown", "winRate", "tradeCount")
                }
        return {"experiment": {"id": exp.id, "name": exp.name, "hypothesis": exp.hypothesis,
                               "baselineRunId": exp.baseline_run_id},
                "runs": summaries, "diff": diff, "deltas": deltas}


def _delta(base: Any, cur: Any) -> Any:
    try:
        if base is None or cur is None:
            return None
        return float(cur) - float(base)
    except (TypeError, ValueError):
        return None


class SweepRequest(BaseModel):
    strategyId: str | None = None
    baseSpec: dict[str, Any] | None = None
    sweepParams: dict[str, list[Any]] = {}
    datasetIds: list[str] = []
    baseConfig: dict[str, Any] = {}


@router.post("/experiments/sweep", status_code=201)
def create_sweep(body: SweepRequest, request: Request) -> JSONResponse:
    from alphalab_contracts import ValidationError

    settings = settings_of(request)
    keys = list(body.sweepParams)
    combos: list[dict[str, Any]] = [{}]
    for key in keys:
        combos = [{**c, key: v} for c in combos for v in body.sweepParams[key]]
        if len(combos) > settings.sweep_max_combos:
            raise ValidationError(f"sweep exceeds {settings.sweep_max_combos} combinations")
    total = len(combos) * max(1, len(body.datasetIds))
    if total > settings.sweep_max_combos:
        raise ValidationError(f"sweep exceeds {settings.sweep_max_combos} runs")
    if not body.datasetIds:
        raise ValidationError("sweep needs at least one datasetId")
    sweep_req = _request_dict_from_config(body.baseConfig)
    run_ids: list[str] = []
    with session_of(request) as session:
        # Resolve the base spec: explicit, or the strategy's current version.
        if body.baseSpec is not None:
            from alphalab_contracts import canonical_json, spec_hash, validate_spec_or_raise

            validate_spec_or_raise(body.baseSpec)
            base_canonical = canonical_json(body.baseSpec)
        elif body.strategyId is not None:
            strategy = session.get(models.Strategy, body.strategyId)
            if strategy is None:
                raise KeyError(f"strategy not found: {body.strategyId}")
            version = session.get(models.StrategyVersion, strategy.current_version_id)
            assert version is not None
            base_canonical = version.spec
        else:
            raise ValidationError("sweep needs baseSpec or strategyId")

        planned: list[tuple[str, str]] = []
        ephemeral_strategy_id: str | None = None
        for combo, dataset_id in itertools.product(combos, body.datasetIds):
            spec = json.loads(base_canonical)
            for path, value in combo.items():
                _set_path(spec, path, value)
            from alphalab_contracts import validate_spec_or_raise as _validate

            _validate(spec)
            if body.strategyId is not None:
                swept = repos.add_strategy_version(
                    session, strategy_id=body.strategyId,
                    spec_json=canonical_json(spec), spec_hash=spec_hash(spec),
                    provenance={"actor": "user", "patchSummary": f"sweep {combo}"},
                )
                planned.append((swept.id, dataset_id))
            else:
                # One shell strategy for the whole sweep, not one per combo.
                if ephemeral_strategy_id is None:
                    shell, _ = repos.create_strategy(
                        session, name="sweep-base", spec_json=canonical_json(spec),
                        spec_hash=spec_hash(spec),
                        template_ref=None, provenance={"actor": "user", "patchSummary": "sweep base"},
                    )
                    ephemeral_strategy_id = shell.id
                swept = repos.add_strategy_version(
                    session, strategy_id=ephemeral_strategy_id,
                    spec_json=canonical_json(spec), spec_hash=spec_hash(spec),
                    provenance={"actor": "user", "patchSummary": f"sweep {combo}"},
                )
                planned.append((swept.id, dataset_id))
        session.commit()  # versions must be visible to the per-run sessions below
    failures: list[dict[str, Any]] = []
    for version_id, dataset_id in planned:
        try:
            run_json, _ = job_runner.execute_sync(settings, version_id, dataset_id, sweep_req)
        except Exception as exc:  # one bad combo must not 500 the whole sweep
            code = getattr(exc, "code", "INTERNAL")
            failures.append({"versionId": version_id, "datasetId": dataset_id,
                             "code": code, "message": str(exc)})
            continue
        run_ids.append(run_json["id"])
    if not run_ids:
        raise ValidationError("sweep produced no runs", {"failures": failures})
    with session_of(request) as session:
        exp = repos.create_experiment(
            session, name=f"sweep {len(run_ids)} runs", run_ids=run_ids,
            baseline_run_id=run_ids[0] if run_ids else None,
            hypothesis=f"params={body.sweepParams} datasets={body.datasetIds}",
        )
        session.commit()
    return JSONResponse({"experiment": {"id": exp.id}, "runIds": run_ids, "failures": failures}, 201)


def _set_path(spec: dict[str, Any], path: str, value: Any) -> None:
    from alphalab_contracts import ValidationError

    node: Any = spec
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            raise ValidationError(f"bad sweep path: {path}")
        node = node[part]
    if not isinstance(node, dict) or parts[-1] not in node:
        raise ValidationError(f"bad sweep path: {path}")
    node[parts[-1]] = value



