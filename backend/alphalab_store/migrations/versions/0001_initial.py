"""0001: initial schema with immutability triggers.

Hand-authored DDL (no autogenerate). Completed rows in strategy_versions,
datasets, and backtest_runs reject UPDATE and DELETE.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _immutable(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END"
    )


def upgrade() -> None:
    op.create_table(
        "strategies",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, server_default="local"),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("template_ref", sa.JSON, nullable=True),
        sa.Column("current_version_id", sa.String, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("strategy_id", sa.String, nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("spec", sa.Text, nullable=False),
        sa.Column("spec_hash", sa.String, nullable=False, unique=True),
        sa.Column("parent_version_id", sa.String, nullable=True),
        sa.Column("provenance", sa.JSON, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "strategy_templates",
        sa.Column("template_id", sa.String, primary_key=True),
        sa.Column("template_version", sa.String, primary_key=True),
        sa.Column("definition", sa.JSON, nullable=False),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, server_default="local"),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("timeframe", sa.String, nullable=False),
        sa.Column("bar_count", sa.Integer, nullable=False),
        sa.Column("start_time", sa.BigInteger, nullable=False),
        sa.Column("end_time", sa.BigInteger, nullable=False),
        sa.Column("bars_hash", sa.String, nullable=False, unique=True),
        sa.Column("source", sa.JSON, nullable=False),
        sa.Column("manifest", sa.JSON, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "dataset_bars",
        sa.Column("dataset_id", sa.String, primary_key=True),
        sa.Column("open_time", sa.BigInteger, primary_key=True),
        sa.Column("o", sa.REAL, nullable=False),
        sa.Column("h", sa.REAL, nullable=False),
        sa.Column("l", sa.REAL, nullable=False),
        sa.Column("c", sa.REAL, nullable=False),
        sa.Column("v", sa.REAL, nullable=False),
    )
    op.create_table(
        "backtest_jobs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("state", sa.String, nullable=False, index=True),
        sa.Column("cancel_requested", sa.Integer, server_default="0"),
        sa.Column("progress", sa.JSON, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("started_at", sa.BigInteger, nullable=True),
        sa.Column("finished_at", sa.BigInteger, nullable=True),
    )
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("job_id", sa.String, nullable=False),
        sa.Column("strategy_version_id", sa.String, nullable=False, index=True),
        sa.Column("dataset_id", sa.String, nullable=False, index=True),
        sa.Column("spec_hash", sa.String, nullable=False),
        sa.Column("dataset_hash", sa.String, nullable=False),
        sa.Column("config_hash", sa.String, nullable=False),
        sa.Column("result_hash", sa.String, nullable=False, unique=True),
        sa.Column("engine_version", sa.String, nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("metrics", sa.JSON, nullable=False),
        sa.Column("equity_curve", sa.JSON, nullable=False),
        sa.Column("full_resolution_hash", sa.String, nullable=False),
        sa.Column("assumptions", sa.JSON, nullable=False),
        sa.Column("warnings", sa.JSON, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "trades",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("run_id", sa.String, nullable=False, index=True),
        sa.Column("entry_bar", sa.Integer, nullable=False),
        sa.Column("exit_bar", sa.Integer, nullable=False),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("qty", sa.String, nullable=False),
        sa.Column("entry_price", sa.String, nullable=False),
        sa.Column("exit_price", sa.String, nullable=False),
        sa.Column("fees", sa.String, nullable=False),
        sa.Column("gross_pnl", sa.String, nullable=False),
        sa.Column("net_pnl", sa.String, nullable=False),
        sa.Column("intended_risk", sa.String, nullable=False),
        sa.Column("realized_risk", sa.String, nullable=False),
        sa.Column("signal_time", sa.BigInteger, nullable=False),
        sa.Column("exit_reason", sa.String, nullable=False),
        sa.Column("ambiguous", sa.Integer, nullable=False),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("run_id", sa.String, nullable=False, index=True),
        sa.Column("signal_bar", sa.Integer, nullable=False),
        sa.Column("fill_bar", sa.Integer, nullable=True),
        sa.Column("kind", sa.String, server_default="market"),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("qty", sa.String, nullable=True),
        sa.Column("state", sa.String, nullable=False),
        sa.Column("fill_price", sa.String, nullable=True),
        sa.Column("fees", sa.String, nullable=True),
    )
    op.create_table(
        "instrument_meta",
        sa.Column("symbol", sa.String, primary_key=True),
        sa.Column("meta_version", sa.String, primary_key=True),
        sa.Column("pip_size", sa.String, nullable=False),
        sa.Column("contract_size", sa.String, nullable=False),
        sa.Column("lot_step", sa.String, nullable=False),
        sa.Column("min_qty", sa.String, nullable=False),
        sa.Column("price_decimals", sa.Integer, nullable=False),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, server_default="local"),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=True),
        sa.Column("run_ids", sa.JSON, nullable=False),
        sa.Column("baseline_run_id", sa.String, nullable=True),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "ai_proposals",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("input_refs", sa.JSON, nullable=False),
        sa.Column("intent", sa.Text, nullable=False),
        sa.Column("patch", sa.JSON, nullable=False),
        sa.Column("validation", sa.JSON, nullable=False),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=True),
        sa.Column("tokens", sa.Integer, nullable=True),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "ai_traces",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("proposal_id", sa.String, nullable=True),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=True),
        sa.Column("prompt_hash", sa.String, nullable=False),
        sa.Column("response_hash", sa.String, nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False),
        sa.Column("tokens_out", sa.Integer, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "ai_cache",
        sa.Column("provider", sa.String, primary_key=True),
        sa.Column("model", sa.String, primary_key=True),
        sa.Column("cache_key", sa.String, primary_key=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("tokens", sa.Integer, nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
    )
    _immutable("strategy_versions")
    _immutable("datasets")
    _immutable("backtest_runs")


def downgrade() -> None:
    raise NotImplementedError("MVP migrations are forward-only")
