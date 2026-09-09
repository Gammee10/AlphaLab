"""Purity gate: alphalab_core may import stdlib + numpy only.

AGENTS.md / ARCHITECTURE.md §2: any I/O, web, ORM, HTTP, or AI import inside
alphalab_core fails the build. Validation deps (jsonschema/pydantic) belong in
alphalab_contracts or outer layers.
"""

from __future__ import annotations

import ast
from pathlib import Path

BANNED_TOP_LEVELS = {
    "fastapi",
    "sqlalchemy",
    "httpx",
    "google",
    "generativeai",
    "pydantic",
    "jsonschema",
    "requests",
    "aiohttp",
    "flask",
    "django",
    "starlette",
    "uvicorn",
}

CORE_DIR = Path(__file__).resolve().parent.parent / "alphalab_core"


def _top_level(name: str) -> str:
    return name.split(".")[0]


def test_core_has_no_banned_imports() -> None:
    violations: list[str] = []
    for path in sorted(CORE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = _top_level(alias.name)
                    if top in BANNED_TOP_LEVELS:
                        violations.append(f"{path.name}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = _top_level(node.module)
                    if top in BANNED_TOP_LEVELS:
                        violations.append(f"{path.name}:{node.lineno} imports from {node.module}")
    assert not violations, "purity violations in alphalab_core:\n" + "\n".join(violations)


def test_core_package_exists() -> None:
    assert CORE_DIR.is_dir()
