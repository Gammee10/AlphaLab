"""Database engine, sessions, and programmatic migration entrypoint."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def default_db_path() -> Path:
    return Path(
        os.environ.get("ALPHALAB_DB", str(Path.cwd().parent / "data" / "alphalab.sqlite3"))
    )


def make_engine(db_path: Path | None = None) -> Engine:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _wal(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def session_factory(db_path: Path | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(db_path), expire_on_commit=False)


def migrate(db_path: Path | None = None) -> None:
    """Apply all pending Alembic revisions (forward-only, hand-authored DDL)."""
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    command.upgrade(config, "head")


if __name__ == "__main__":
    migrate()
