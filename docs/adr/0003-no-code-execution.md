# ADR 0003 — No execution of AI-generated or user-supplied code

## Context
AI proposes strategy content. Any code-execution path turns prompt injection into RCE.

## Decision
There is **no code path**: no `eval`, `new Function`, dynamic import of user strings, or plugin loader in MVP. This is a lint-enforced ban, not a convention. Strategies are data; templates are shipped code reviewed like any other source.

## Consequences
+ Entire threat class removed; security review stays proportional to MVP.
− Users cannot bring custom indicators yet. Future path (if ever): WASM-sandboxed indicator registry with explicit permission model — requires its own ADR and is out of MVP.
