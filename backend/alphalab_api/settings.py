"""Runtime settings (env-overridable, localhost defaults)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str = "127.0.0.1"
    port: int = 4100
    sync_bar_threshold: int = 200_000
    job_concurrency: int = 2
    job_queue_limit: int = 20
    job_timeout_s: int = 120
    sweep_max_combos: int = 32
    max_trades_per_run: int = 50_000


def load_settings(db_path: Path | str | None = None) -> Settings:
    root = Path(__file__).resolve().parent.parent.parent
    default_db = Path(os.environ.get("ALPHALAB_DB", str(root / "data" / "alphalab.sqlite3")))
    return Settings(db_path=Path(db_path) if db_path else default_db)
