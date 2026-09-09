"""FastAPI application factory with startup recovery and template seeding."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import select

from alphalab_contracts import AlphaLabError
from alphalab_core.templates import PARAM_SCHEMAS, TEMPLATES
from alphalab_marketdata import DatasetInvalid as MarketDatasetInvalid
from alphalab_store import models, repos
from alphalab_store.database import migrate, session_factory

from .deps import alphalab_error_handler
from .routes_ai import router as ai_router
from .routes_catalog import router as catalog_router
from .routes_runs import router as runs_router
from .service import TooManyTrades
from .settings import Settings, load_settings


def seed_templates(factory: Any) -> None:
    """Registry rows follow template code; a code-less registry id fails boot."""
    with factory() as session:
        known = {t.template_id for t in session.scalars(select(models.StrategyTemplate)).all()}
        for tid, t in TEMPLATES.items():
            if tid not in known:
                session.add(models.StrategyTemplate(
                    template_id=tid, template_version=t["version"],
                    definition={"displayName": t["displayName"], "description": t["description"],
                                "paramSchema": PARAM_SCHEMAS[tid]},
                ))
        orphans = [
            t.template_id for t in session.scalars(select(models.StrategyTemplate)).all()
            if t.template_id not in TEMPLATES
        ]
        if orphans:
            raise RuntimeError(f"template registry has code-less ids: {orphans}")
        session.commit()


def create_app(db_path: Path | str | None = None) -> FastAPI:
    settings = load_settings(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        migrate(settings.db_path)
        seed_templates(app.state.session_factory)
        with app.state.session_factory() as session:
            repos.recover_interrupted(session)
            session.commit()
        yield

    app = FastAPI(title="AlphaLab", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory(settings.db_path)
    app.include_router(catalog_router)
    app.include_router(runs_router)
    app.include_router(ai_router)
    for exc in (AlphaLabError, KeyError, TooManyTrades, MarketDatasetInvalid):
        app.add_exception_handler(exc, alphalab_error_handler)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "time": int(time.time() * 1000)}

    return app


def main() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run("alphalab_api.app:create_app", host=settings.host, port=settings.port, factory=True)


if __name__ == "__main__":
    main()
