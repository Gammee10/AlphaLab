"""SQLAlchemy 2 table registry (docs/persistence.md).

Money is TEXT (Decimal canonical); market bars are REAL; times are INTEGER
UTC ms. Immutability of strategy_versions/datasets/backtest_runs is enforced
by SQLite triggers created in the Alembic migration (defense in depth with
the repo guards).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, REAL, BigInteger, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default="local")
    name: Mapped[str] = mapped_column(String)
    template_ref: Mapped[dict[str, Any] | None] = mapped_column("template_ref", JSON, nullable=True)
    current_version_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    spec: Mapped[str] = mapped_column(Text)  # canonical JSON
    spec_hash: Mapped[str] = mapped_column(String, index=True)  # content-addressed, not unique (0002)
    parent_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger)


class StrategyTemplate(Base):
    __tablename__ = "strategy_templates"
    template_id: Mapped[str] = mapped_column(String, primary_key=True)
    template_version: Mapped[str] = mapped_column(String, primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default="local")
    symbol: Mapped[str] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String)
    bar_count: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[int] = mapped_column(BigInteger)
    end_time: Mapped[int] = mapped_column(BigInteger)
    bars_hash: Mapped[str] = mapped_column(String, unique=True)
    source: Mapped[dict[str, Any]] = mapped_column(JSON)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger)


class DatasetBar(Base):
    __tablename__ = "dataset_bars"
    dataset_id: Mapped[str] = mapped_column(String, primary_key=True)
    open_time: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    o: Mapped[float] = mapped_column("o", REAL)
    h: Mapped[float] = mapped_column("h", REAL)
    l: Mapped[float] = mapped_column("l", REAL)
    c: Mapped[float] = mapped_column("c", REAL)
    v: Mapped[float] = mapped_column("v", REAL)


class BacktestJob(Base):
    __tablename__ = "backtest_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[str] = mapped_column(String, index=True)
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger)
    started_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String)
    strategy_version_id: Mapped[str] = mapped_column(String, index=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    spec_hash: Mapped[str] = mapped_column(String)
    dataset_hash: Mapped[str] = mapped_column(String)
    config_hash: Mapped[str] = mapped_column(String)
    result_hash: Mapped[str] = mapped_column(String, unique=True)
    engine_version: Mapped[str] = mapped_column(String)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    equity_curve: Mapped[list[Any]] = mapped_column(JSON)
    full_resolution_hash: Mapped[str] = mapped_column(String)
    assumptions: Mapped[list[Any]] = mapped_column(JSON)
    warnings: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger)


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    entry_bar: Mapped[int] = mapped_column(Integer)
    exit_bar: Mapped[int] = mapped_column(Integer)
    entry_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    exit_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    direction: Mapped[str] = mapped_column(String)
    qty: Mapped[str] = mapped_column(String)
    entry_price: Mapped[str] = mapped_column(String)
    exit_price: Mapped[str] = mapped_column(String)
    fees: Mapped[str] = mapped_column(String)
    gross_pnl: Mapped[str] = mapped_column(String)
    net_pnl: Mapped[str] = mapped_column(String)
    intended_risk: Mapped[str] = mapped_column(String)
    realized_risk: Mapped[str] = mapped_column(String)
    signal_time: Mapped[int] = mapped_column(BigInteger)
    exit_reason: Mapped[str] = mapped_column(String)
    ambiguous: Mapped[int] = mapped_column(Integer)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    signal_bar: Mapped[int] = mapped_column(Integer)
    fill_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String, default="market")
    direction: Mapped[str] = mapped_column(String)
    qty: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String)
    fill_price: Mapped[str | None] = mapped_column(String, nullable=True)
    fees: Mapped[str | None] = mapped_column(String, nullable=True)


class InstrumentMeta(Base):
    __tablename__ = "instrument_meta"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    meta_version: Mapped[str] = mapped_column(String, primary_key=True)
    pip_size: Mapped[str] = mapped_column(String)
    contract_size: Mapped[str] = mapped_column(String)
    lot_step: Mapped[str] = mapped_column(String)
    min_qty: Mapped[str] = mapped_column(String)
    price_decimals: Mapped[int] = mapped_column(Integer)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default="local")
    name: Mapped[str] = mapped_column(String)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_ids: Mapped[list[Any]] = mapped_column(JSON)
    baseline_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class AiProposal(Base):
    __tablename__ = "ai_proposals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    input_refs: Mapped[dict[str, Any]] = mapped_column(JSON)
    intent: Mapped[str] = mapped_column(Text)
    patch: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class AiTrace(Base):
    __tablename__ = "ai_traces"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String)
    response_hash: Mapped[str] = mapped_column(String)
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(BigInteger)


class AiCache(Base):
    __tablename__ = "ai_cache"
    provider: Mapped[str] = mapped_column(String, primary_key=True)
    model: Mapped[str] = mapped_column(String, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(BigInteger)
