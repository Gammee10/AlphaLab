# ADR 0010 — Gemini model selection: Flash default, Pro opt-in

## Context
Within the free-tier decision (ADR 0008), which Gemini models do what? Update (2026-09): `gemini-2.5-flash`/`-pro` were deprecated for new API keys (404 "no longer available to new users"). The decision below is unchanged; only the pinned model names moved to the current GA generation.

## Decision
- `propose` (strategy patches) and `explain`: **Flash only** (`gemini-3.8-flash`). Patches are schema-constrained JSON where Flash's instruction-following at low temperature is sufficient; routing Pro here would burn the scarcer quota for no measured gain.
- `summarize` / multi-run compare: **Flash default, Pro opt-in toggle per call** (`gemini-pro-latest`). Pro's deeper reasoning helps causal-leaning summaries ("why did performance break after 2022?"), but the output stays grounded to cited metrics either way — Pro gets no exemption from the grounding check.
- Token budgets enforced server-side regardless of model; Pro calls blocked when its separate budget is exhausted (falls back to Flash, then to ruled, with disclosure at each step).

## Consequences
Flash quota carries daily use; Pro reserved for the one call type where depth plausibly matters. Model names are pinned in `alphalab_ai/gemini.py` with a deprecation note — when Google retires a generation again, the 404 body ("no longer available to new users") surfaces through `ModelError` and the fix is a two-line constant change.
