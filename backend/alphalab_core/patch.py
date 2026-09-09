"""Atomic strategy-patch application (docs/ai-assistant.md, domain-model.md).

``apply_patch`` transforms a base spec into a new spec from allowlisted ops.
Atomicity: work happens on a deep copy; any inapplicable op raises PatchError
and the base is untouched. Final schema validation is the caller's job
(alphalab_contracts, which core must not import).
"""

from __future__ import annotations

import copy
from typing import Any, cast

MAX_OPS = 10

_SET_PARAM_TARGETS = (
    "exits.stopLoss.atrMultiplier",
    "exits.stopLoss.pips",
    "exits.takeProfit.ratio",
    "exits.takeProfit.atrMultiplier",
    "exits.trailing.atrMultiplier",
    "exits.trailing.activationR",
    "exits.timeStop.bars",
    "exits.oppositeSignalExit",
    "risk.riskPerTradePct",
    "risk.maxNotionalMult",
    "risk.leverageMax",
    "risk.minStopPriceDistance",
    "filters.spreadMaxBps",
    "filters.session.startHourUtc",
    "filters.session.endHourUtc",
    "filters.volatility.minAtr",
    "filters.volatility.maxAtr",
    "entry.direction",
    "entry.logic",
)

_INDICATOR_FIELDS = ("period", "fast", "slow", "signal", "stdDev", "atrMultiplier")


class PatchError(Exception):
    code = "AI_VALIDATION_FAILED"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _navigate(spec: dict[str, Any], dotted: str) -> tuple[dict[str, Any], str]:
    parts = dotted.split(".")
    node: Any = spec
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node or not isinstance(node[part], dict):
            raise PatchError(f"unknown patch target: {dotted}")
        node = node[part]
    if not isinstance(node, dict) or parts[-1] not in node:
        raise PatchError(f"unknown patch target: {dotted}")
    return node, parts[-1]


def _find_group(conditions: list[Any], group_id: str | None) -> list[Any]:
    if group_id is None:
        return conditions
    stack = list(conditions)
    while stack:
        node = stack.pop()
        if isinstance(node, dict) and "group" in node:
            if node.get("id") == group_id:
                return cast(list[Any], node["children"])
            stack.extend(node.get("children", []))
    raise PatchError(f"unknown parent group: {group_id}")


def _collect_ids(conditions: list[Any]) -> set[str]:
    ids: set[str] = set()
    stack = list(conditions)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("id") is not None:
                ids.add(node["id"])
            if "group" in node:
                stack.extend(node.get("children", []))
    return ids


def _remove(conditions: list[Any], cond_id: str) -> bool:
    for i, node in enumerate(conditions):
        if isinstance(node, dict) and node.get("id") == cond_id and "group" not in node:
            del conditions[i]
            return True
        if isinstance(node, dict) and "group" in node:
            if _remove(node["children"], cond_id):
                return True
    return False


def apply_patch(base_spec: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    if len(ops) > MAX_OPS:
        raise PatchError(f"patch has {len(ops)} ops; max is {MAX_OPS}")
    spec = copy.deepcopy(base_spec)
    for op in ops:
        kind = op.get("op")
        if kind == "setParam":
            target = op.get("target", "")
            if target in _SET_PARAM_TARGETS:
                node, leaf = _navigate(spec, target)
                node[leaf] = op.get("value")
            elif target.startswith("indicators."):
                _, ref, field = target.split(".", 2) if target.count(".") == 2 else (None, None, None)
                if ref is None or field not in _INDICATOR_FIELDS:
                    raise PatchError(f"unknown patch target: {target}")
                found = [i for i in spec.get("indicators", []) if i.get("id") == ref]
                if not found or field not in found[0]:
                    raise PatchError(f"unknown patch target: {target}")
                found[0][field] = op.get("value")
            else:
                raise PatchError(f"unknown patch target: {target}")
        elif kind == "setRisk":
            field = op.get("field", "")
            if field not in ("riskPerTradePct", "maxNotionalMult", "leverageMax", "minStopPriceDistance"):
                raise PatchError(f"unknown risk field: {field}")
            spec["risk"][field] = op.get("value")
        elif kind == "setExits":
            value = op.get("value")
            if not isinstance(value, dict):
                raise PatchError("setExits needs an object value")
            spec["exits"] = value
        elif kind == "addCondition":
            condition = op.get("condition")
            if not isinstance(condition, dict) or "id" not in condition:
                raise PatchError("addCondition needs a condition with an id")
            if condition["id"] in _collect_ids(spec["entry"]["conditions"]):
                raise PatchError(f"duplicate condition id: {condition['id']}")
            _find_group(spec["entry"]["conditions"], op.get("parentGroupId")).append(condition)
        elif kind == "addGroup":
            group = {"id": op.get("id"), "group": op.get("logic", "all"), "children": op.get("children", [])}
            if not group["id"] or group["id"] in _collect_ids(spec["entry"]["conditions"]):
                raise PatchError(f"bad group id: {group['id']}")
            if group["group"] not in ("all", "any"):
                raise PatchError(f"bad group logic: {group['group']}")
            _find_group(spec["entry"]["conditions"], op.get("parentGroupId")).append(group)
        elif kind == "removeCondition":
            if not _remove(spec["entry"]["conditions"], op.get("id", "")):
                raise PatchError(f"condition not found: {op.get('id')}")
        elif kind == "addFilter":
            name, value = op.get("filter", ""), op.get("value")
            if name not in ("session", "volatility", "spreadMaxBps") or not isinstance(value, dict) and name != "spreadMaxBps":
                raise PatchError(f"unknown filter: {name}")
            spec.setdefault("filters", {})[name] = value
        elif kind == "removeFilter":
            if op.get("filter") not in ("session", "volatility", "spreadMaxBps"):
                raise PatchError(f"unknown filter: {op.get('filter')}")
            spec.setdefault("filters", {})[op["filter"]] = (
                {"kind": "none"} if op["filter"] != "spreadMaxBps" else None
            )
        else:
            raise PatchError(f"unknown op: {kind}")
    return spec
