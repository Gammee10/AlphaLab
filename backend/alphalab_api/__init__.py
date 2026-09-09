"""AlphaLab HTTP API (docs/api.md). Thin orchestration over deterministic core."""

from .app import create_app

__all__ = ["create_app"]
