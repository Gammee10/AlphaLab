# AlphaLab backend

Polyglot repo layout (see `ARCHITECTURE.md §2`, ADR 0009):

```text
backend/
  alphalab_core/        # PURE engine: stdlib + numpy only (purity test enforced)
  alphalab_contracts/   # canonical schema loading, validation, canonicalization, hashing
  alphalab_api/         # (later slice) FastAPI routes, jobs, orchestration
  alphalab_store/       # (later slice) SQLAlchemy models, Alembic migrations
  alphalab_ai/          # (later slice) AIAssistant port, ruled + gemini providers
  tests/                # pytest: fixtures, golden vectors, hypothesis properties
shared/schemas/         # canonical JSON Schema — the cross-language contract
```

## Why `alphalab_contracts` exists

`alphalab_core` is restricted to stdlib + numpy (no `jsonschema`, no `pydantic`).
Schema validation therefore lives one layer out, in `alphalab_contracts`, which
validates raw dicts against `shared/schemas/strategy.spec.json` and hands
already-valid data to core. The purity test (`tests/test_purity.py`) enforces this.
