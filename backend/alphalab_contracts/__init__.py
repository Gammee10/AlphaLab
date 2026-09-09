"""Canonical schema loading, StrategySpec validation, hashing.

Validation lives here (not in alphalab_core) because it needs the
``jsonschema`` third-party package, which the core purity rule forbids.
"""

from .canonical import canonical_json, canonicalize, content_hash
from .errors import (
    AlphaLabError,
    DatasetInvalidError,
    ErrorPayload,
    NotSupportedError,
    StrategyInvalidError,
    ValidationError,
    ValidationIssue,
)
from .runs import config_hash, result_hash
from .strategy import check_run_compatibility, load_schema, spec_hash, validate_spec, validate_spec_or_raise

__all__ = [
    "AlphaLabError",
    "DatasetInvalidError",
    "ErrorPayload",
    "NotSupportedError",
    "StrategyInvalidError",
    "ValidationError",
    "ValidationIssue",
    "canonical_json",
    "canonicalize",
    "check_run_compatibility",
    "config_hash",
    "content_hash",
    "load_schema",
    "result_hash",
    "spec_hash",
    "validate_spec",
    "validate_spec_or_raise",
]
