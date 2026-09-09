"""Market-data import pipeline (docs/market-data.md).

CSV -> parse -> normalize (tz to UTC ms, sort, keep-first dedupe) -> validate
(grid alignment, OHLC order, finite positives) -> gap scan -> manifest + hash.

Rejected rows are reported, never auto-fixed. Missing bars stay absent.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from alphalab_core.bars import BarArrays

TIMEFRAME_MS = {"M5": 300_000, "M15": 900_000, "H1": 3_600_000, "H4": 14_400_000, "D1": 86_400_000}
H4_HOURS = (0, 4, 8, 12, 16, 20)
MAX_ROWS = 2_000_000
MAX_BYTES = 25 * 1024 * 1024


@dataclass
class BarRow:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Gap:
    start_ms: int
    end_ms: int
    missing_bars: int


@dataclass
class DatasetManifest:
    symbol: str
    timeframe: str
    rows_received: int = 0
    rows_stored: int = 0
    duplicates_dropped: int = 0
    rows_rejected: list[dict[str, object]] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    bars_hash: str = ""


class DatasetInvalid(Exception):
    code = "DATASET_INVALID"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _parse_time(raw: str, line: int) -> int:
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise DatasetInvalid(f"line {line}: bad open_time {raw!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def _parse_float(raw: str, name: str, line: int) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise DatasetInvalid(f"line {line}: bad {name} {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise DatasetInvalid(f"line {line}: non-finite {name}")
    return value


def grid_aligned(open_time_ms: int, timeframe: str) -> bool:
    dt = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)
    if dt.second != 0 or dt.microsecond != 0:
        return False
    if timeframe == "M5":
        return dt.minute % 5 == 0
    if timeframe == "M15":
        return dt.minute % 15 == 0
    if timeframe == "H1":
        return dt.minute == 0
    if timeframe == "H4":
        return dt.minute == 0 and dt.hour in H4_HOURS
    if timeframe == "D1":
        return dt.minute == 0 and dt.hour == 0
    raise DatasetInvalid(f"unknown timeframe {timeframe!r}")


def import_csv(
    text: str,
    symbol: str,
    timeframe: str,
    max_rows: int = MAX_ROWS,
    max_bytes: int = MAX_BYTES,
) -> tuple[list[BarRow], DatasetManifest]:
    if timeframe not in TIMEFRAME_MS:
        raise DatasetInvalid(f"unknown timeframe {timeframe!r}")
    if len(text.encode("utf-8")) > max_bytes:
        raise DatasetInvalid(f"file exceeds {max_bytes} bytes; split by year/symbol")
    manifest = DatasetManifest(symbol=symbol, timeframe=timeframe)
    # utf-8-sig strips a BOM if present.
    reader = csv.DictReader(io.StringIO(text.encode("utf-8").decode("utf-8-sig")))
    expected = ["open_time", "open", "high", "low", "close", "volume"]
    if (reader.fieldnames or []) != expected:
        raise DatasetInvalid(f"header must be exactly: {','.join(expected)}")
    seen: set[int] = set()
    ordered: dict[int, BarRow] = {}
    line = 1  # header
    for record in reader:
        line += 1
        manifest.rows_received += 1
        if manifest.rows_received > max_rows:
            raise DatasetInvalid(f"file exceeds {max_rows} rows; split by year/symbol")
        try:
            ts = _parse_time(str(record["open_time"]), line)
            o = _parse_float(record["open"], "open", line)
            h = _parse_float(record["high"], "high", line)
            low = _parse_float(record["low"], "low", line)
            c = _parse_float(record["close"], "close", line)
            v = _parse_float(record["volume"], "volume", line)
        except DatasetInvalid as exc:
            manifest.rows_rejected.append({"line": line, "reason": exc.message})
            continue
        if ts in seen:
            manifest.duplicates_dropped += 1
            continue
        seen.add(ts)
        problems: list[str] = []
        if o <= 0 or h <= 0 or low <= 0 or c <= 0:
            problems.append("non-positive price")
        if h < max(o, c) or low > min(o, c):
            problems.append("high/low inconsistent with open/close")
        if v < 0:
            problems.append("negative volume")
        if not grid_aligned(ts, timeframe):
            problems.append("open_time not on timeframe grid")
        if problems:
            manifest.rows_rejected.append({"line": line, "reason": "; ".join(problems)})
            continue
        ordered[ts] = BarRow(ts, o, h, low, c, v)
    rows = [ordered[ts] for ts in sorted(ordered)]
    manifest.rows_stored = len(rows)
    step = TIMEFRAME_MS[timeframe]
    for prev, cur in zip(rows, rows[1:]):
        if cur.open_time - prev.open_time > step:
            manifest.gaps.append(
                Gap(prev.open_time, cur.open_time, cur.open_time // step - prev.open_time // step - 1)
            )
    manifest.bars_hash = hash_rows(rows)
    return rows, manifest


def hash_rows(rows: list[BarRow]) -> str:
    canonical = json.dumps(
        [[r.open_time, r.open, r.high, r.low, r.close, r.volume] for r in rows],
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def has_volume(rows: list[BarRow]) -> bool:
    return any(r.volume > 0 for r in rows)


def to_bar_arrays(rows: list[BarRow]) -> BarArrays:
    return BarArrays(
        open_time=np.array([r.open_time for r in rows], dtype=np.int64),
        open=np.array([r.open for r in rows], dtype=np.float64),
        high=np.array([r.high for r in rows], dtype=np.float64),
        low=np.array([r.low for r in rows], dtype=np.float64),
        close=np.array([r.close for r in rows], dtype=np.float64),
        volume=np.array([r.volume for r in rows], dtype=np.float64),
    )


def select_range(
    rows: list[BarRow], start_ms: int, end_ms: int, warmup_bars: int
) -> tuple[list[BarRow], bool, int]:
    """Bars over [start-lookback, end] with trade window [start, end].

    Returns (window_rows, cold_start, deficit): cold_start is True when fewer
    than warmup_bars pre-bars exist (engine seeds from whatever is available
    and the run carries the warning).
    """
    idx = next((i for i, r in enumerate(rows) if r.open_time >= start_ms), len(rows))
    take = max(0, idx - warmup_bars)
    window = [r for r in rows[take:] if r.open_time <= end_ms]
    deficit = warmup_bars - (idx - take)
    return window, deficit > 0, max(0, deficit)
