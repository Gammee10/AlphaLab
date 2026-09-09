"""One-shot generator for tests/fixtures/templates/*.json (template defaults)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from alphalab_core.templates import TEMPLATES, instantiate  # noqa: E402


def main() -> None:
    dest = BACKEND / "tests" / "fixtures" / "templates"
    dest.mkdir(parents=True, exist_ok=True)
    for tid in TEMPLATES:
        path = dest / f"{tid}.json"
        path.write_text(json.dumps(instantiate(tid, {}), indent=1), encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
