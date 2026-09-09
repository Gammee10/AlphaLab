"""Market-data tests: CSV edges, validation, gaps, hashing, synthetic."""

from __future__ import annotations

import pytest

from alphalab_marketdata import (
    DatasetInvalid,
    grid_aligned,
    hash_rows,
    has_volume,
    import_csv,
    select_range,
    to_bar_arrays,
)
from alphalab_marketdata.synthetic import generate_synthetic

GOOD = """open_time,open,high,low,close,volume
2024-01-02T00:00:00Z,1.10,1.11,1.09,1.105,0
2024-01-02T00:15:00Z,1.105,1.12,1.10,1.115,0
2024-01-02T00:30:00Z,1.115,1.12,1.11,1.112,0
"""


def test_import_happy_path() -> None:
    rows, manifest = import_csv(GOOD, "EURUSD", "M15")
    assert manifest.rows_received == 3 and manifest.rows_stored == 3
    assert manifest.duplicates_dropped == 0 and manifest.rows_rejected == []
    assert manifest.gaps == [] and len(manifest.bars_hash) == 64
    assert [r.open_time for r in rows] == sorted(r.open_time for r in rows)


def test_bom_crlf_and_tz_offsets() -> None:
    text = "﻿open_time,open,high,low,close,volume\r\n2024-01-02T02:00:00+02:00,1.10,1.11,1.09,1.105,0\r\n"
    rows, manifest = import_csv(text, "EURUSD", "M15")
    assert manifest.rows_stored == 1
    assert rows[0].open_time == 1704153600000  # == 2024-01-02T00:00:00Z


def test_duplicates_keep_first() -> None:
    dup = GOOD + "2024-01-02T00:15:00Z,9.99,9.99,9.99,9.99,0\n"
    rows, manifest = import_csv(dup, "EURUSD", "M15")
    assert manifest.duplicates_dropped == 1 and manifest.rows_stored == 3
    assert rows[1].open == 1.105  # first occurrence wins, deterministically


def test_bad_rows_rejected_not_fixed() -> None:
    bad = GOOD + "2024-01-02T00:45:00Z,1.10,1.09,1.11,1.105,0\n"  # high/low inverted
    rows, manifest = import_csv(bad, "EURUSD", "M15")
    assert manifest.rows_stored == 3 and len(manifest.rows_rejected) == 1
    assert "inconsistent" in manifest.rows_rejected[0]["reason"]


def test_grid_misalignment_rejected() -> None:
    off = GOOD + "2024-01-02T00:07:00Z,1.10,1.11,1.09,1.105,0\n"
    rows, manifest = import_csv(off, "EURUSD", "M15")
    assert manifest.rows_stored == 3
    assert any("grid" in r["reason"] for r in manifest.rows_rejected)


def test_header_and_caps() -> None:
    with pytest.raises(DatasetInvalid, match="header"):
        import_csv("a,b,c\n1,2,3\n", "EURUSD", "M15")
    with pytest.raises(DatasetInvalid, match="exceeds 2 rows"):
        import_csv(GOOD, "EURUSD", "M15", max_rows=2)
    with pytest.raises(DatasetInvalid):
        import_csv(GOOD, "EURUSD", "W1")


def test_gap_scan() -> None:
    gapped = GOOD + "2024-01-02T02:00:00Z,1.10,1.11,1.09,1.105,0\n"
    _, manifest = import_csv(gapped, "EURUSD", "M15")
    assert len(manifest.gaps) == 1
    assert manifest.gaps[0].missing_bars == 5  # 00:30 -> 02:00 skips 5x15m


def test_hash_determinism_and_sensitivity() -> None:
    rows, manifest = import_csv(GOOD, "EURUSD", "M15")
    assert hash_rows(rows) == manifest.bars_hash
    rows2, _ = import_csv(GOOD.replace("1.115", "1.116"), "EURUSD", "M15")
    assert hash_rows(rows2) != manifest.bars_hash
    assert not has_volume(rows)
    assert has_volume([rows[0].__class__(rows[0].open_time, 1, 2, 1, 2, 5.0)])


def test_grid_rules() -> None:
    assert grid_aligned(1704153600000, "M15")  # 2024-01-02T00:00Z
    assert not grid_aligned(1704153600000 + 60_000, "M15")
    assert grid_aligned(1704153600000, "H1") and grid_aligned(1704153600000, "H4")
    assert not grid_aligned(1704153600000 + 3_600_000, "H4")  # 01:00 not an H4 boundary
    assert grid_aligned(1704153600000, "D1")
    assert not grid_aligned(1704153600000 + 3_600_000, "D1")


def test_select_range_and_cold_start() -> None:
    rows, _ = import_csv(GOOD, "EURUSD", "M15")
    window, cold, deficit = select_range(rows, rows[2].open_time, rows[2].open_time, 50)
    assert cold and deficit == 48 and len(window) == 3
    window2, cold2, deficit2 = select_range(rows, rows[1].open_time, rows[2].open_time, 1)
    assert not cold2 and deficit2 == 0 and len(window2) == 3


def test_synthetic_determinism() -> None:
    a = generate_synthetic("EURUSD", "M15", "2024-01-01T00:00:00Z", 50, 7, 1.1)
    b = generate_synthetic("EURUSD", "M15", "2024-01-01T00:00:00Z", 50, 7, 1.1)
    c = generate_synthetic("EURUSD", "M15", "2024-01-01T00:00:00Z", 50, 8, 1.1)
    assert [(r.open_time, r.close) for r in a] == [(r.open_time, r.close) for r in b]
    assert [r.close for r in a] != [r.close for r in c]
    assert import_csv(
        "open_time,open,high,low,close,volume\n" + "\n".join(
            "2024-01-01T00:00:00Z,1,2,1,2,0" for _ in range(1)
        ) + "\n",
        "EURUSD", "M15",
    )[1].rows_stored == 1


def test_to_bar_arrays_roundtrip() -> None:
    rows, _ = import_csv(GOOD, "EURUSD", "M15")
    bars = to_bar_arrays(rows)
    assert len(bars) == 3
    assert list(bars.close) == [1.105, 1.115, 1.112]

