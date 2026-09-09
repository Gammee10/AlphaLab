# ADR 0002 — Declarative JSON strategy representation

## Context
Brief requires reusable templates + safe AI modification + reproducibility. Representation choice determines all three.

## Options
A) Executable strategy code (TS/Python functions). B) Expression DSL / scripting. C) Declarative JSON spec + allowlisted operands. D) Visual rule-tree stored as JSON (superset of C with UI metadata).

## Decision
**C** (with D as a frontend rendering of the same JSON, not a separate model). Spec: `docs/strategy-spec.md`. AI edits via allowlisted `StrategyPatch` ops only. Adversarial review (2026-09-09) extended C with **nested condition groups** (depth ≤ 3, ≤12 leaves, no NOT-over-groups): flat-only AND/OR would have forced a future migration for routine compositions like "trend AND (A OR B)". Flat specs remain valid as the implicit top-level group — no migration.

## Consequences
+ Schema validation, exact hashing/diffing, no sandbox, AI cannot silently reprogram semantics; templates are pure constructors.
− Expressiveness ceiling (no custom indicators/patterns in v1). Accepted deliberately: ceiling is visible (`NOT_SUPPORTED_IN_MVP`) rather than a leaky DSL. Custom-indicator extension goes through a future `engine/2.0` ADR with a registration API, not string code.
