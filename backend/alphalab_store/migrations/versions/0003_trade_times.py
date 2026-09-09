"""0003: persist trade entry/exit times (chart markers need them; payload has them)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_trade_times"
down_revision = "0002_spec_hash_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("entry_time", sa.BigInteger, nullable=True))
    op.add_column("trades", sa.Column("exit_time", sa.BigInteger, nullable=True))


def downgrade() -> None:
    raise NotImplementedError("MVP migrations are forward-only")
