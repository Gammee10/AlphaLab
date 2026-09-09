"""Typed errors shared by the backend. Codes match docs/api.md exactly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    code: str
    message: str


class AlphaLabError(Exception):
    code: str = "INTERNAL"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class StrategyInvalidError(AlphaLabError):
    code = "STRATEGY_INVALID"

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        first = issues[0] if issues else ValidationIssue("", "STRATEGY_INVALID", "invalid strategy")
        super().__init__(
            f"{first.path}: {first.message}" if first.path else first.message,
            {"issues": [vars(i) for i in issues]},
        )


class NotSupportedError(AlphaLabError):
    code = "NOT_SUPPORTED_IN_MVP"


class DatasetInvalidError(AlphaLabError):
    code = "DATASET_INVALID"


@dataclass
class ErrorPayload:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
