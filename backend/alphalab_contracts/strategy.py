"""StrategySpec v1 validation.

Two layers (docs/strategy-spec.md):
- structural: canonical JSON Schema (types, enums, ranges) via ``jsonschema``
- semantic: cross-field rules with typed error codes (refs, groups, MACD, windows)

``validate_spec`` never raises; ``validate_spec_or_raise`` raises
``StrategyInvalidError``. ``check_run_compatibility`` covers rules that need
dataset context (VWAP volume). Session/timeframe compatibility is spec-intrinsic
and validated here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from .canonical import content_hash
from .errors import NotSupportedError, StrategyInvalidError, ValidationIssue

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "shared" / "schemas" / "strategy.spec.json"

_MAX_CONDITION_LEAVES = 12
_MAX_GROUP_DEPTH = 3
_MAX_INDICATORS = 8
_SESSIONLESS_TIMEFRAMES = ("H4", "D1")
_KNOWN_OPERAND_KINDS = ("indicator", "price", "const")
_KNOWN_INDICATOR_KINDS = ("EMA", "SMA", "RSI", "ATR", "MACD", "BB", "ADX", "Donchian", "VWAP")
_MULTI_OUTPUTS = {
    "MACD": ("macd", "signal", "histogram"),
    "BB": ("upper", "middle", "lower"),
    "Donchian": ("upper", "lower", "middle"),
}


def load_schema(path: Path | None = None) -> dict[str, Any]:
    with open(path or _SCHEMA_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def _walk_nodes(conditions: list[Any]) -> Iterator[tuple[Any, int]]:
    """Yield (node, depth) for every node; branch children nest one deeper."""
    stack: list[tuple[Any, int]] = [(c, 1) for c in conditions]
    while stack:
        node, depth = stack.pop()
        yield node, depth
        if isinstance(node, dict) and "group" in node:
            children = node.get("children") or []
            for child in children:
                stack.append((child, depth + 1))


def _walk_operands(conditions: list[Any]) -> Iterator[Any]:
    for node, _ in _walk_nodes(conditions):
        if isinstance(node, dict) and "left" in node:
            yield node.get("left")
            yield node.get("right")


def validate_spec(spec: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(spec, dict):
        return [ValidationIssue("", "STRATEGY_INVALID", "spec must be an object")]

    conditions = spec.get("entry", {}).get("conditions", []) if isinstance(spec.get("entry"), dict) else []

    # Pre-scan: lookahead offsets and unknown operand kinds get specific codes
    # before generic schema validation.
    for operand in _walk_operands(conditions if isinstance(conditions, list) else []):
        if not isinstance(operand, dict):
            continue
        kind = operand.get("kind")
        if kind not in _KNOWN_OPERAND_KINDS:
            issues.append(
                ValidationIssue(
                    "entry.conditions", "NOT_SUPPORTED_IN_MVP", f"unsupported operand kind: {kind!r}"
                )
            )
        offset = operand.get("offsetBars", 0)
        if isinstance(offset, int) and offset < 0:
            issues.append(
                ValidationIssue(
                    "entry.conditions",
                    "LOOKAHEAD_OFFSET_REJECTED",
                    f"negative offsetBars ({offset}) would read future bars",
                )
            )

    # Structural validation against the canonical schema.
    schema = load_schema()
    validator = Draft202012Validator(schema)
    for error in validator.iter_errors(spec):
        path = ".".join(str(p) for p in error.absolute_path)
        issues.append(ValidationIssue(path, "STRATEGY_INVALID", error.message))
    if issues:
        return issues

    # Semantic checks (schema passed, shapes are trustworthy).
    indicators = spec["indicators"]
    ids = [i["id"] for i in indicators]
    if len(set(ids)) != len(ids):
        issues.append(ValidationIssue("indicators", "STRATEGY_INVALID", "indicator ids must be unique"))
    id_set = set(ids)
    for node, depth in _walk_nodes(spec["entry"]["conditions"]):
        if depth > _MAX_GROUP_DEPTH:
            issues.append(
                ValidationIssue(
                    "entry.conditions", "STRATEGY_INVALID", f"condition nesting exceeds depth {_MAX_GROUP_DEPTH}"
                )
            )
            break
    leaves = [n for n, _ in _walk_nodes(spec["entry"]["conditions"]) if "left" in n]
    if not 1 <= len(leaves) <= _MAX_CONDITION_LEAVES:
        issues.append(
            ValidationIssue(
                "entry.conditions",
                "STRATEGY_INVALID",
                f"must have 1..{_MAX_CONDITION_LEAVES} leaf conditions, found {len(leaves)}",
            )
        )
    seen: set[str] = set()
    for node, _ in _walk_nodes(spec["entry"]["conditions"]):
        nid = node.get("id")
        if nid in seen:
            issues.append(
                ValidationIssue("entry.conditions", "STRATEGY_INVALID", f"duplicate condition id: {nid!r}")
            )
            break
        seen.add(nid)
    for leaf in leaves:
        for side in ("left", "right"):
            op = leaf[side]
            if op["kind"] == "indicator" and op["ref"] not in id_set:
                issues.append(
                    ValidationIssue(
                        "entry.conditions", "STRATEGY_INVALID", f"unknown indicator ref: {op['ref']!r}"
                    )
                )
    by_id = {i["id"]: i for i in indicators}
    for leaf in leaves:
        for side in ("left", "right"):
            op = leaf[side]
            if op["kind"] != "indicator" or op["ref"] not in by_id:
                continue
            kind = by_id[op["ref"]]["kind"]
            allowed = _MULTI_OUTPUTS.get(kind)
            output = op.get("output")
            if allowed is None:
                if output is not None and output != "value":
                    issues.append(
                        ValidationIssue(
                            "entry.conditions",
                            "STRATEGY_INVALID",
                            f"single-output indicator {op['ref']!r} takes no output selector",
                        )
                    )
            elif output not in allowed:
                issues.append(
                    ValidationIssue(
                        "entry.conditions",
                        "STRATEGY_INVALID",
                        f"{kind} output must be one of {allowed}, got {output!r}",
                    )
                )
    exits = spec["exits"]
    uses_atr = any(
        exits[slot].get("kind") == "atr" for slot in ("stopLoss", "takeProfit", "trailing") if isinstance(exits.get(slot), dict)
    )
    if uses_atr and not any(i["kind"] == "ATR" for i in indicators):
        issues.append(
            ValidationIssue(
                "exits",
                "STRATEGY_INVALID",
                "atr-based exits require at least one declared ATR indicator "
                "(the first declared ATR is used for sizing and trailing)",
            )
        )
    for ind in indicators:
        if ind["kind"] == "MACD" and not ind["fast"] < ind["slow"]:
            issues.append(
                ValidationIssue("indicators", "STRATEGY_INVALID", "MACD requires fast < slow")
            )

    filters = spec.get("filters") or {}
    session = (filters.get("session") or {"kind": "none"}).copy()
    if session.get("kind") == "window":
        if session["startHourUtc"] == session["endHourUtc"]:
            issues.append(
                ValidationIssue(
                    "filters.session", "STRATEGY_INVALID", "session window must have non-zero length"
                )
            )
        if spec["universe"]["timeframe"] in _SESSIONLESS_TIMEFRAMES:
            issues.append(
                ValidationIssue(
                    "filters.session",
                    "NOT_SUPPORTED_IN_MVP",
                    f"session windows are meaningless on {spec['universe']['timeframe']} "
                    "(bar granularity defeats the concept); use M5/M15",
                )
            )
    volatility = filters.get("volatility") or {"kind": "none"}
    if volatility.get("kind") == "atr-range":
        lo, hi = volatility.get("minAtr"), volatility.get("maxAtr")
        if lo is not None and hi is not None and lo > hi:
            issues.append(
                ValidationIssue(
                    "filters.volatility", "STRATEGY_INVALID", "minAtr must not exceed maxAtr"
                )
            )

    reserved = spec.get("reservedForFuture")
    if reserved:
        issues.append(
            ValidationIssue(
                "reservedForFuture",
                "NOT_SUPPORTED_IN_MVP",
                "partials, pyramiding and limit/stop entries are not supported in MVP (engine/1.0)",
            )
        )
    return issues


def validate_spec_or_raise(spec: dict[str, Any]) -> dict[str, Any]:
    issues = validate_spec(spec)
    if not issues:
        return spec
    blocking = [i for i in issues if i.code != "NOT_SUPPORTED_IN_MVP"]
    if blocking:
        raise StrategyInvalidError(blocking)
    raise NotSupportedError(issues[0].message, {"issues": [vars(i) for i in issues]})


def spec_hash(spec: dict[str, Any]) -> str:
    return content_hash(spec)


def check_run_compatibility(spec: dict[str, Any], *, has_volume: bool) -> list[ValidationIssue]:
    """Rules needing dataset context. VWAP requires nonzero volume (rule 4c)."""
    issues: list[ValidationIssue] = []
    kinds = {i["kind"] for i in spec.get("indicators", [])}
    if "VWAP" in kinds and not has_volume:
        issues.append(
            ValidationIssue(
                "indicators",
                "DATASET_INVALID",
                "VWAP requires volume data; this dataset is volume-less (FX/metals carry no volume)",
            )
        )
    return issues
