"""0002: spec_hash is content-addressable, not globally unique.

Two strategies may share one spec (duplicate/fork); run-level result_hash
remains the dedupe key. Replace the UNIQUE constraint with a plain index.
"""

from __future__ import annotations

from alembic import op

revision = "0002_spec_hash_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE strategy_versions_new ("
        "id TEXT NOT NULL PRIMARY KEY, strategy_id TEXT NOT NULL, "
        "version_number INTEGER NOT NULL, spec TEXT NOT NULL, spec_hash TEXT NOT NULL, "
        "parent_version_id TEXT, provenance JSON NOT NULL, created_at BIGINT NOT NULL)"
    )
    op.execute(
        "INSERT INTO strategy_versions_new "
        "(id, strategy_id, version_number, spec, spec_hash, parent_version_id, provenance, created_at) "
        "SELECT id, strategy_id, version_number, spec, spec_hash, parent_version_id, provenance, created_at "
        "FROM strategy_versions"
    )
    op.execute("DROP TABLE strategy_versions")
    op.execute("ALTER TABLE strategy_versions_new RENAME TO strategy_versions")
    op.execute("CREATE INDEX ix_strategy_versions_strategy_id ON strategy_versions (strategy_id)")
    op.execute("CREATE INDEX ix_strategy_versions_spec_hash ON strategy_versions (spec_hash)")
    op.execute(
        "CREATE TRIGGER trg_strategy_versions_no_update BEFORE UPDATE ON strategy_versions "
        "BEGIN SELECT RAISE(ABORT, 'strategy_versions is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_strategy_versions_no_delete BEFORE DELETE ON strategy_versions "
        "BEGIN SELECT RAISE(ABORT, 'strategy_versions is immutable'); END"
    )


def downgrade() -> None:
    raise NotImplementedError("MVP migrations are forward-only")
