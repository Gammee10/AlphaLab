# ADR 0010 — Gemini model selection: Flash default, Pro opt-in

## Context
Within the free-tier decision (ADR 0008), which Gemini model does what? Flash and Pro differ on free quota size, latency, and reasoning depth.

## Decision
- `propose` (strategy patches) and `explain`: **Flash only**. Patches are schema-constrained JSON where Flash's instruction-following at low temperature is sufficient; routing Pro here would burn the scarcer quota for no measured gain.
- `summarize` / multi-run compare: **Flash default, Pro opt-in toggle per call**. Pro's deeper reasoning helps causal-leaning summaries ("why did performance break after 2022?"), but the output stays grounded to cited metrics either way — Pro gets no exemption from the grounding check.
- Token budgets enforced server-side regardless of model; Pro calls blocked when its separate budget is exhausted (falls back to Flash, then to ruled, with disclosure at each step).

## Consequences
Flash quota carries daily use; Pro reserved for the one call type where depth plausibly matters. If measured quality shows Flash sufficient for summaries too, Pro toggle can be removed without touching the port.
