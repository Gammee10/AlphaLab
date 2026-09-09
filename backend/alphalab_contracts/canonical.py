"""Canonicalization and content hashing for versioned artifacts.

Rules (docs/strategy-spec.md, docs/persistence.md):
- sort object keys recursively
- round every float to 6 decimal places (ints, strings, bools untouched)
- normalize ``reservedForFuture`` absence vs ``{}`` to absent
- UTF-8 JSON with minimal separators, sha256 hex
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def _round_floats(value: Any) -> Any:
    if isinstance(value, Decimal):
        return round(float(value), 6)  # hashes stabilize at 6dp; money exactness lives in tests
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: _round_floats(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round_floats(v) for v in value]
    return value


def canonicalize(spec: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in spec.items() if k != "reservedForFuture" or v}
    if "reservedForFuture" in cleaned and not cleaned["reservedForFuture"]:
        del cleaned["reservedForFuture"]
    rounded = _round_floats(cleaned)
    assert isinstance(rounded, dict)
    return rounded


def canonical_json(spec: dict[str, Any]) -> str:
    return json.dumps(canonicalize(spec), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(spec: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()
