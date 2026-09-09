"""Persistence tests: migrations, repos, immutability triggers, atomicity."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alphalab_contracts import content_hash
from alphalab_core.config import Costs
from alphalab_marketdata import BarRow

from alphalab_store import repos
from alphalab_store.database import migrate, session_factory


@pytest.fixture()
def session(tmp_path: Path):
    migrate(tmp_path / "test.sqlite3")
    factory = session_factory(tmp_path / "test.sqlite3")
    with factory() as s:
        yield s
        s.rollback()


def rows() -> list[BarRow]:
    return [BarRow(1_700_000_000_000 + i * 900_000, 100 + i, 101 + i, 99 + i, 100 + i, 0.0) for i in range(5)]


def test_migrate_twice_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite3"
    migrate(db)
    migrate(db)
    factory = session_factory(db)
    with factory() as s:
        tables = {r[0] for r in s.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"strategies", "datasets", "dataset_bars", "backtest_runs", "trades", "orders"} <= tables


def test_strategy_version_chain_and_immutability(session) -> None:
    s, v1 = repos.create_strategy(
        session, name="s", spec_json='{"a":1}', spec_hash="h1",
        template_ref=None, provenance={"actor": "user"},
    )
    assert v1.version_number == 1 and s.current_version_id == v1.id
    v2 = repos.add_strategy_version(
        session, strategy_id=s.id, spec_json='{"a":2}', spec_hash="h2", provenance={"actor": "user"}
    )
    assert v2.version_number == 2 and v2.parent_version_id == v1.id
    session.commit()
    with pytest.raises(Exception, match="immutable"):
        session.execute(text("UPDATE strategy_versions SET spec_hash='x' WHERE id=:i"), {"i": v1.id})


def test_dataset_roundtrip_ordered_and_hash(session) -> None:
    data = rows()
    ds = repos.create_dataset(
        session, symbol="EURUSD", timeframe="M15", rows=data,
        bars_hash="abc", source={"kind": "csv"}, manifest={},
    )
    session.commit()
    assert repos.get_dataset_by_hash(session, "abc").id == ds.id
    back = repos.get_dataset_bars(session, ds.id)
    assert [(r.open_time, r.close) for r in back] == [(r.open_time, r.close) for r in data]
    with pytest.raises(Exception, match="immutable"):
        session.execute(text("DELETE FROM datasets WHERE id=:i"), {"i": ds.id})


def test_run_insert_atomic_and_dedupe(session) -> None:
    from alphalab_core.config import RunPayload

    ds = repos.create_dataset(session, symbol="BTCUSD", timeframe="M15", rows=rows(),
                              bars_hash="b", source={}, manifest={})
    _, v = repos.create_strategy(session, name="s", spec_json="{}", spec_hash="sh",
                                 template_ref=None, provenance={})
    job = repos.create_job(session)
    payload = RunPayload(trades=[], orders=[], equity=[(1, Decimal("10"))],
                         warnings={}, assumptions=[])
    run = repos.insert_run(
        session, job_id=job.id, strategy_version_id=v.id, dataset_id=ds.id,
        spec_hash="sh", dataset_hash="b", config_hash="c", result_hash="r1",
        engine_version="engine/1.0", config={"a": 1},
        metrics={"netProfit": Decimal("150.5")}, payload=payload,
    )
    session.commit()
    assert repos.get_run_by_result_hash(session, "r1").id == run.id
    stored = repos.get_run(session, run.id)
    assert stored.metrics["netProfit"] == "150.5"  # Decimal crosses as TEXT
    assert stored.equity_curve == [[1, "10"]]
    # Duplicate result hash violates uniqueness: the idempotency-race contract.
    with pytest.raises(IntegrityError):
        repos.insert_run(
            session, job_id=job.id, strategy_version_id=v.id, dataset_id=ds.id,
            spec_hash="sh", dataset_hash="b", config_hash="c", result_hash="r1",
            engine_version="engine/1.0", config={}, metrics={}, payload=payload,
        )
        session.flush()
    session.rollback()
    with pytest.raises(Exception, match="immutable"):
        session.execute(text("UPDATE backtest_runs SET config_hash='x' WHERE id=:i"), {"i": run.id})


def test_job_lifecycle_cancel_recover(session) -> None:
    job = repos.create_job(session)
    assert job.state == "queued"
    repos.set_job_running(session, job.id, 100)
    repos.set_job_progress(session, job.id, 40)
    assert repos.request_cancel(session, job.id).cancel_requested == 1
    assert repos.request_cancel(session, "missing") is None
    repos.finish_job(session, job.id, "cancelled")
    assert repos.request_cancel(session, job.id) is None  # terminal: not cancellable
    job2 = repos.create_job(session)
    repos.set_job_running(session, job2.id, 10)
    session.commit()
    assert repos.recover_interrupted(session) == 1
    assert repos.recover_interrupted(session) == 0


def test_session_factory_cached_per_path(tmp_path: Path) -> None:
    from alphalab_store.database import (
        dispose_session_factories,
        get_session_factory,
    )

    a = tmp_path / "a.sqlite3"
    b = tmp_path / "b.sqlite3"
    assert get_session_factory(a) is get_session_factory(a)
    assert get_session_factory(a) is not get_session_factory(b)
    # Usable after dispose (pools reopen on demand).
    dispose_session_factories()
    with get_session_factory(a)() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1


def test_downsample_bound_and_stable() -> None:
    equity = [(i, Decimal(i)) for i in range(5000)]
    curve = repos.downsample_equity(equity)
    assert len(curve) == 2000
    assert curve == repos.downsample_equity(equity)
    assert repos.full_resolution_hash(equity) == repos.full_resolution_hash(list(equity))
    assert repos.full_resolution_hash(equity) != repos.full_resolution_hash(equity[:-1])


def test_content_hash_contract() -> None:
    assert content_hash({"b": 1, "a": [1.5, 2]}) == content_hash({"a": [1.5, 2], "b": 1})
