"""AI routes: propose/confirm/explain/summarize/status (docs/api.md, ai-assistant.md).

Every response carries provider/model/token metadata. Gemini output goes
through the identical validation + grounding + confirm pipeline as ruled
output. Raw model text is never applied and never persisted as a version.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from alphalab_contracts import (
    ValidationError,
    canonical_json,
    spec_hash,
    validate_spec_or_raise,
)
from alphalab_core.patch import PatchError, apply_patch
from alphalab_store import models, repos

from .deps import session_of, settings_of
from .settings import Settings

router = APIRouter(prefix="/api/ai")


def _live_request_fn(url: str, body: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=body)
        if response.status_code == 429:
            return {"status": 429}
        out = response.json() if response.content else {}
        out["status"] = response.status_code
        out["body"] = response.text[:400]
        return out


def _select_provider(settings: Settings, key: str | None) -> str:
    if settings.ai_provider == "ruled":
        return "ruled"
    if settings.ai_provider == "gemini" and key:
        return "gemini"
    if settings.ai_provider == "auto" and key:
        return "gemini"
    return "ruled"


def _current_spec(session: Session, version_id: str) -> tuple[dict[str, Any], str]:
    version = repos.get_strategy_version(session, version_id)
    if version is None:
        raise KeyError(f"strategy version not found: {version_id}")
    return json.loads(version.spec), version.spec_hash


class ProposeRequest(BaseModel):
    strategyVersionId: str | None = None
    runIds: list[str] = []
    intent: str = ""


@router.post("/propose")
def propose(body: ProposeRequest, request: Request) -> dict[str, Any]:
    from alphalab_ai import gemini, ruled
    from alphalab_api.settings import gemini_key

    settings = settings_of(request)
    key = gemini_key()
    provider = _select_provider(settings, key)
    with session_of(request) as session:
        spec = None
        base_hash = ""
        if body.strategyVersionId is not None:
            spec, base_hash = _current_spec(session, body.strategyVersionId)
        fallback_reason = None
        if provider == "gemini" and key is not None:
            try:
                patch = gemini.propose(spec, body.intent, key, _live_request_fn)
            except gemini.QuotaExhausted:
                provider = "ruled"
                fallback_reason = "quota"
            except gemini.ModelError as exc:
                raise ValidationError(f"AI output rejected: {exc}") from None
        if provider == "ruled":
            raw = ruled.propose(spec, body.intent)
            patch = {"ops": raw["ops"], "rationale": raw.get("rationale", ""),
                     "provider": ruled.PROVIDER, "model": ruled.MODEL, "tokens": 0}
            if raw.get("rationale") == "clarifier":
                patch["message"] = raw.get("message", "")
        # Validate ops structurally (no application yet).
        try:
            if spec is not None and patch["ops"]:
                validate_spec_or_raise(apply_patch(spec, patch["ops"]))
            validation: dict[str, Any] = {"ok": True, "errors": []}
        except Exception as exc:  # surfaced in validation payload, never applied
            code = getattr(exc, "code", "AI_VALIDATION_FAILED")
            validation = {"ok": False, "errors": [{"code": code, "message": str(exc)}]}
        row = repos.save_proposal(
            session, input_refs={"strategyVersionId": body.strategyVersionId, "runIds": body.runIds},
            intent=body.intent, patch={"ops": patch["ops"], "rationale": patch.get("rationale", ""),
                                       "baseSpecHash": base_hash},
            validation=validation, provider=patch.get("provider", provider),
            model=patch.get("model"), tokens=patch.get("tokens"),
        )
        session.commit()
        out: dict[str, Any] = {"proposal": {"id": row.id, "status": row.status,
                                            "patch": row.patch, "validation": validation,
                                            "provider": row.provider, "model": row.model,
                                            "tokens": row.tokens}}
        if fallback_reason:
            out["proposal"]["fallbackReason"] = fallback_reason
        if patch.get("message"):
            out["proposal"]["message"] = patch["message"]
        return out


class ConfirmRequest(BaseModel):
    proposalId: str


@router.post("/confirm")
def confirm(body: ConfirmRequest, request: Request) -> JSONResponse:
    with session_of(request) as session:
        proposal = session.get(models.AiProposal, body.proposalId)
        if proposal is None:
            return JSONResponse({"code": "NOT_FOUND", "message": "proposal not found", "details": {}}, 404)
        if proposal.status != "proposed":
            return JSONResponse({"code": "AI_VALIDATION_FAILED", "message": f"proposal is {proposal.status}",
                                 "details": {}}, 409)
        version_id = proposal.input_refs.get("strategyVersionId")
        if version_id is None:
            raise ValidationError("proposal targets no strategy version")
        version = repos.get_strategy_version(session, version_id)
        if version is None:
            raise KeyError(f"strategy version not found: {version_id}")
        strategy = session.get(models.Strategy, version.strategy_id)
        current = repos.get_strategy_version(session, strategy.current_version_id) if strategy else version
        assert current is not None
        if proposal.patch.get("baseSpecHash") != current.spec_hash:
            proposal.status = "rejected"
            session.commit()
            return JSONResponse({"code": "STALE_PATCH",
                                 "message": "strategy changed since this proposal; re-propose",
                                 "details": {}}, 409)
        if not proposal.validation.get("ok"):
            return JSONResponse({"code": "AI_VALIDATION_FAILED", "message": "proposal failed validation",
                                 "details": proposal.validation}, 400)
        try:
            new_spec = apply_patch(json.loads(current.spec), proposal.patch["ops"])
            validate_spec_or_raise(new_spec)
        except PatchError as exc:
            return JSONResponse({"code": "AI_VALIDATION_FAILED", "message": str(exc), "details": {}}, 400)
        strategy_id = current.strategy_id
        new_version = repos.add_strategy_version(
            session, strategy_id=strategy_id, spec_json=canonical_json(new_spec),
            spec_hash=spec_hash(new_spec),
            provenance={"actor": "ai-assistant", "patchSummary": proposal.patch.get("rationale", ""),
                        "aiTraceId": proposal.id},
        )
        proposal.status = "confirmed"
        session.commit()
        return JSONResponse({"version": {"id": new_version.id, "versionNumber": new_version.version_number,
                                         "specHash": new_version.spec_hash}})


class ExplainRequest(BaseModel):
    strategyVersionId: str


@router.post("/explain")
def explain(body: ExplainRequest, request: Request) -> dict[str, Any]:
    from alphalab_ai import gemini, ruled
    from alphalab_api.settings import gemini_key

    settings = settings_of(request)
    key = gemini_key()
    with session_of(request) as session:
        spec, spec_hash_value = _current_spec(session, body.strategyVersionId)
        cache_key = gemini.cache_key("explain", spec_hash_value)
        cached = repos.cache_get(session, "gemini" if key else "ruled",
                                 gemini.MODEL_PROPOSE if key else ruled.MODEL, cache_key)
        if cached is not None:
            cached_out: dict[str, Any] = json.loads(cached.payload)
            cached_out["cached"] = True
            return cached_out
        provider = _select_provider(settings, key)
        fallback_reason = None
        if provider == "gemini" and key is not None:
            try:
                result = gemini.explain(spec, key, _live_request_fn)
            except gemini.QuotaExhausted:
                provider = "ruled"
                fallback_reason = "quota"
            except gemini.ModelError as exc:
                raise ValidationError(f"AI output rejected: {exc}") from None
        if provider == "ruled":
            result = ruled.explain(spec)
        footer = {"provider": result["provider"], "model": result["model"],
                  "tokens": result.get("tokens", 0), "groundedIn": {"specHash": spec_hash_value}}
        if fallback_reason:
            footer["fallbackReason"] = fallback_reason
        repos.cache_set(session, result["provider"], result["model"], cache_key,
                        json.dumps({"text": result["text"], "citations": result.get("citations", []),
                                    **footer}), result.get("tokens", 0))
        session.commit()
        return {"text": result["text"], "citations": result.get("citations", []), **footer}


class SummarizeRequest(BaseModel):
    runIds: list[str]
    usePro: bool = False


@router.post("/summarize")
def summarize(body: SummarizeRequest, request: Request) -> dict[str, Any]:
    from alphalab_ai import gemini, ruled
    from alphalab_api.settings import gemini_key

    settings = settings_of(request)
    key = gemini_key()
    with session_of(request) as session:
        runs: list[dict[str, Any]] = []
        for rid in body.runIds[:4]:
            run = repos.get_run(session, rid)
            if run is None:
                raise KeyError(f"run not found: {rid}")
            runs.append({"runId": run.id, "metrics": dict(run.metrics), "warnings": dict(run.warnings),
                         "specHash": run.spec_hash, "resultHash": run.result_hash})
        if not runs:
            raise ValidationError("summarize needs at least one runId")
        cache_key = gemini.cache_key("summarize", *[str(r["resultHash"]) for r in runs])
        cached = repos.cache_get(session, "gemini" if key else "ruled",
                                 gemini.MODEL_SUMMARIZE, cache_key)
        if cached is not None:
            out: dict[str, Any] = json.loads(cached.payload)
            out["cached"] = True
            return out
        provider = _select_provider(settings, key)
        fallback_reason = None
        if provider == "gemini" and key is not None:
            try:
                result = gemini.summarize(runs, key, _live_request_fn, pro=body.usePro)
            except gemini.QuotaExhausted:
                provider = "ruled"
                fallback_reason = "quota"
            except gemini.ModelError as exc:
                raise ValidationError(f"AI output rejected: {exc}") from None
        if provider == "ruled":
            first = runs[0]
            result = ruled.summarize(dict(first["metrics"]), dict(first["warnings"]),
                                     [str(r["runId"]) for r in runs])
        footer = {"provider": result["provider"], "model": result["model"],
                  "tokens": result.get("tokens", 0),
                  "groundedIn": {"runIds": [str(r["runId"]) for r in runs]}}
        if fallback_reason:
            footer["fallbackReason"] = fallback_reason
        repos.cache_set(session, result["provider"], result["model"], cache_key,
                        json.dumps({"text": result["text"], "citations": result.get("citations", []),
                                    **footer}), result.get("tokens", 0))
        session.commit()
        return {"text": result["text"], "citations": result.get("citations", []), **footer}


@router.get("/status")
def ai_status(request: Request) -> dict[str, Any]:
    import os

    from alphalab_api.settings import gemini_key

    settings = settings_of(request)
    configured = gemini_key() is not None or "GEMINI_API_KEY" in os.environ
    active = _select_provider(settings, "x" if configured else None)
    return {"provider": active, "keyConfigured": configured,
            "quota": {"note": "free-tier enforced provider-side; daily input budget configured server-side"}}
