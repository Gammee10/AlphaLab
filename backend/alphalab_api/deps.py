"""Shared route dependencies and error mapping (docs/api.md error model)."""

from __future__ import annotations

from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from alphalab_contracts import AlphaLabError, NotSupportedError, StrategyInvalidError
from alphalab_marketdata import DatasetInvalid as MarketDatasetInvalid
from alphalab_store.database import session_factory

from .service import TooManyTrades
from .settings import Settings


def settings_of(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def session_of(request: Request) -> Session:
    factory: sessionmaker[Session] = request.app.state.session_factory
    return factory()


async def alphalab_error_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    if isinstance(exc, StrategyInvalidError):
        return JSONResponse({"code": "STRATEGY_INVALID", "message": exc.message, "details": exc.details}, 400)
    if isinstance(exc, NotSupportedError):
        return JSONResponse({"code": "NOT_SUPPORTED_IN_MVP", "message": exc.message, "details": exc.details}, 400)
    if isinstance(exc, (MarketDatasetInvalid,)) or type(exc).__name__ == "DatasetInvalidError":
        return JSONResponse({"code": "DATASET_INVALID", "message": getattr(exc, "message", str(exc)), "details": {}}, 400)
    if isinstance(exc, AlphaLabError):
        return JSONResponse({"code": exc.code, "message": exc.message, "details": exc.details}, 400)
    if isinstance(exc, KeyError):
        return JSONResponse({"code": "NOT_FOUND", "message": str(exc), "details": {}}, 404)
    if isinstance(exc, TooManyTrades):
        return JSONResponse({"code": "TOO_MANY_TRADES", "message": exc.message, "details": {}}, 400)
    return JSONResponse({"code": "INTERNAL", "message": "internal error", "details": {}}, 500)
