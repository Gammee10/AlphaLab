"""Async job path: process-pool execution, cancel, timeout (spawn-safe)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select

from alphalab_api import jobs as job_runner
from alphalab_api.settings import load_settings
from alphalab_store import models, repos
from alphalab_store.database import migrate, session_factory

from test_api import CSV, M15, SPEC, T0, make_dataset, make_strategy


@pytest.fixture()
def settings(tmp_path: Path):
    from fastapi.testclient import TestClient

    from alphalab_api.app import create_app

    app = create_app(tmp_path / "jobs.sqlite3")
    with TestClient(app) as client:
        yield load_settings(tmp_path / "jobs.sqlite3"), client


def _ids(client):
    return make_strategy(client), make_dataset(client)


def _request() -> dict:
    return {"startTime": T0, "endTime": T0 + 2 * M15, "initialCapital": "10000", "costs": None,
            "inSample": None, "outOfSample": None}


def test_async_completes_with_run(settings) -> None:
    config, client = settings
    version_id, dataset_id = _ids(client)
    factory = session_factory(config.db_path)
    with factory() as session:
        job = repos.create_job(session)
        session.commit()
        job_id = job.id
    asyncio.run(job_runner.execute_async(config, job_id, version_id, dataset_id, _request()))
    with factory() as session:
        job = session.get(models.BacktestJob, job_id)
        assert job.state == "completed"
        assert job.progress["runId"]
        run = repos.get_run(session, job.progress["runId"])
        assert run.metrics["tradeCount"] == 1


def test_async_cancel_before_start(settings) -> None:
    config, client = settings
    version_id, dataset_id = _ids(client)
    factory = session_factory(config.db_path)
    with factory() as session:
        job = repos.create_job(session)
        session.commit()
        job_id = job.id
        repos.request_cancel(session, job_id)
        session.commit()
    asyncio.run(job_runner.execute_async(config, job_id, version_id, dataset_id, _request()))
    with factory() as session:
        job = session.get(models.BacktestJob, job_id)
        assert job.state == "cancelled"
        assert session.query(models.BacktestRun).count() == 0


def test_sync_engine_failure_finalizes_job(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    config, client = settings
    version_id, dataset_id = _ids(client)
    factory = session_factory(config.db_path)

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(job_runner, "run_backtest", boom)
    with pytest.raises(RuntimeError, match="boom"):
        job_runner.execute_sync(config, version_id, dataset_id, _request())
    with factory() as session:
        jobs = session.scalars(select(models.BacktestJob)).all()
        assert jobs and all(j.state == "failed" for j in jobs)
        # Unknown failure: generic code persisted, internals never stored.
        assert all(j.error == "INTERNAL: internal error" for j in jobs)
    assert job_runner.queued_depth(config) == 0


def test_recover_heals_queued_and_running(settings) -> None:
    config, _ = settings
    factory = session_factory(config.db_path)
    with factory() as session:
        queued = repos.create_job(session)
        running = repos.create_job(session)
        repos.set_job_running(session, running.id, 10)
        session.commit()
        assert repos.recover_interrupted(session) == 2
        session.commit()
    with factory() as session:
        assert session.get(models.BacktestJob, queued.id).state == "failed"
        assert session.get(models.BacktestJob, running.id).state == "failed"
    assert job_runner.queued_depth(config) == 0


def test_sync_slots_exhausted_429(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    config, client = settings
    version_id, dataset_id = _ids(client)
    monkeypatch.setattr(job_runner, "_sync_slots", threading.Semaphore(0))
    monkeypatch.setattr(job_runner, "_sync_slots_key", config.job_concurrency)
    r = client.post("/api/backtests", json={
        "strategyVersionId": version_id, "datasetId": dataset_id,
        "config": {"startTime": T0, "endTime": T0 + 2 * M15, "initialCapital": "10000"}})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"
    assert job_runner.queued_depth(config) == 0  # busy rows are terminal, never queue


def test_sync_admission_respects_queue_limit(settings) -> None:
    config, client = settings
    version_id, dataset_id = _ids(client)
    factory = session_factory(config.db_path)
    with factory() as session:
        for _ in range(config.job_queue_limit):
            repos.create_job(session)
        session.commit()
    r = client.post("/api/backtests", json={
        "strategyVersionId": version_id, "datasetId": dataset_id,
        "config": {"startTime": T0, "endTime": T0 + 2 * M15, "initialCapital": "10000"}})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"


def test_async_invalid_spec_fails_job(settings) -> None:
    config, client = settings
    dataset_id = make_dataset(client)
    factory = session_factory(config.db_path)
    with factory() as session:
        job = repos.create_job(session)
        session.commit()
        job_id = job.id
    asyncio.run(job_runner.execute_async(config, job_id, "missing-version", dataset_id, _request()))
    with factory() as session:
        job = session.get(models.BacktestJob, job_id)
        assert job.state == "failed" and job.error
        assert job.error.startswith("NOT_FOUND")
