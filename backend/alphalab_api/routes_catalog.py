"""Template, strategy, and dataset routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from alphalab_contracts import ValidationError, canonical_json, spec_hash, validate_spec_or_raise
from alphalab_core.templates import PARAM_SCHEMAS, TEMPLATES, describe, instantiate
from alphalab_marketdata import import_csv
from alphalab_store import models, repos

from .deps import session_of

router = APIRouter(prefix="/api")


@router.get("/templates")
def list_templates() -> dict[str, Any]:
    return {
        "templates": [
            {
                "templateId": tid,
                "templateVersion": t["version"],
                "displayName": t["displayName"],
                "description": t["description"],
                "paramSchema": PARAM_SCHEMAS[tid],
            }
            for tid, t in TEMPLATES.items()
        ]
    }


class CreateStrategy(BaseModel):
    name: str
    templateId: str | None = None
    params: dict[str, Any] = {}
    spec: dict[str, Any] | None = None  # blank path: client-built spec (same validation)


@router.post("/strategies", status_code=201)
def create_strategy(body: CreateStrategy, request: Request) -> dict[str, Any]:
    template_ref = None
    if body.templateId is not None:
        try:
            spec = instantiate(body.templateId, body.params)
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
        template = TEMPLATES[body.templateId]
        template_ref = {"templateId": body.templateId, "templateVersion": template["version"], "params": body.params}
    elif body.spec is not None:
        spec = body.spec
    else:
        raise ValidationError("provide templateId+params or a full spec")
    validate_spec_or_raise(spec)
    canonical = canonical_json(spec)
    with session_of(request) as session:
        strategy, version = repos.create_strategy(
            session, name=body.name, spec_json=canonical, spec_hash=spec_hash(spec),
            template_ref=template_ref, provenance={"actor": "user"},
        )
        session.commit()
        result = {"strategy": {"id": strategy.id, "name": strategy.name, "currentVersionId": version.id}}
    return result


@router.get("/strategies")
def list_strategies(request: Request) -> dict[str, Any]:
    from sqlalchemy import select

    with session_of(request) as session:
        rows = session.scalars(select(models.Strategy)).all()
        return {"strategies": [{"id": s.id, "name": s.name, "currentVersionId": s.current_version_id} for s in rows]}


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str, request: Request) -> dict[str, Any]:
    from sqlalchemy import select

    with session_of(request) as session:
        strategy = session.get(models.Strategy, strategy_id)
        if strategy is None:
            raise KeyError(f"strategy not found: {strategy_id}")
        versions = session.scalars(
            select(models.StrategyVersion)
            .where(models.StrategyVersion.strategy_id == strategy_id)
            .order_by(models.StrategyVersion.version_number)
        ).all()
        return {
            "strategy": {"id": strategy.id, "name": strategy.name, "currentVersionId": strategy.current_version_id},
            "versions": [
                {"id": v.id, "versionNumber": v.version_number, "specHash": v.spec_hash,
                 "spec": json.loads(v.spec), "provenance": v.provenance, "createdAt": v.created_at}
                for v in versions
            ],
        }


class CreateVersion(BaseModel):
    spec: dict[str, Any]


@router.post("/strategies/{strategy_id}/versions", status_code=201)
def create_version(strategy_id: str, body: CreateVersion, request: Request) -> dict[str, Any]:
    validate_spec_or_raise(body.spec)
    canonical = canonical_json(body.spec)
    with session_of(request) as session:
        version = repos.add_strategy_version(
            session, strategy_id=strategy_id, spec_json=canonical,
            spec_hash=spec_hash(body.spec), provenance={"actor": "user"},
        )
        session.commit()
        return {"version": {"id": version.id, "versionNumber": version.version_number, "specHash": version.spec_hash}}


class ImportDataset(BaseModel):
    filename: str
    csvText: str
    symbol: str
    timeframe: str


@router.post("/datasets/import", status_code=201)
def import_dataset(body: ImportDataset, request: Request) -> dict[str, Any]:
    rows, manifest = import_csv(body.csvText, body.symbol, body.timeframe)
    manifest_json = {
        "rowsReceived": manifest.rows_received, "rowsStored": manifest.rows_stored,
        "duplicatesDropped": manifest.duplicates_dropped,
        "rowsRejected": manifest.rows_rejected,
        "gaps": [g.__dict__ for g in manifest.gaps],
        "barsHash": manifest.bars_hash,
    }
    with session_of(request) as session:
        existing = repos.get_dataset_by_hash(session, manifest.bars_hash)
        if existing is not None:
            return {"dataset": {"id": existing.id, "deduped": True}, "manifest": manifest_json}
        dataset = repos.create_dataset(
            session, symbol=body.symbol, timeframe=body.timeframe, rows=rows,
            bars_hash=manifest.bars_hash,
            source={"kind": "csv", "filename": body.filename},
            manifest=manifest_json,
        )
        session.commit()
        result = {
            "dataset": {"id": dataset.id, "symbol": dataset.symbol, "timeframe": dataset.timeframe,
                        "barCount": dataset.bar_count, "barsHash": dataset.bars_hash},
            "manifest": manifest_json,
        }
    return result


@router.get("/datasets")
def list_datasets(request: Request) -> dict[str, Any]:
    from sqlalchemy import select

    with session_of(request) as session:
        rows = session.scalars(select(models.Dataset)).all()
        return {"datasets": [
            {"id": d.id, "symbol": d.symbol, "timeframe": d.timeframe, "barCount": d.bar_count,
             "startTime": d.start_time, "endTime": d.end_time, "barsHash": d.bars_hash} for d in rows
        ]}


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, request: Request) -> dict[str, Any]:
    with session_of(request) as session:
        dataset = session.get(models.Dataset, dataset_id)
        if dataset is None:
            raise KeyError(f"dataset not found: {dataset_id}")
        bars = repos.get_dataset_bars(session, dataset_id)[:100]
        return {
            "dataset": {"id": dataset.id, "symbol": dataset.symbol, "timeframe": dataset.timeframe,
                        "barCount": dataset.bar_count, "barsHash": dataset.bars_hash},
            "manifest": dataset.manifest,
            "sample": [
                {"openTime": b.open_time, "open": b.open, "high": b.high, "low": b.low,
                 "close": b.close, "volume": b.volume} for b in bars
            ],
        }


@router.get("/templates/{template_id}/preview")
def template_preview(template_id: str, request: Request) -> dict[str, Any]:
    del request
    if template_id not in TEMPLATES:
        raise KeyError(f"template not found: {template_id}")
    return {"describe": describe(template_id, {}), "spec": instantiate(template_id, {})}
