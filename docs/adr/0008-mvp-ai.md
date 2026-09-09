# ADR 0008 — MVP AI: free-tier Gemini (BYOK) primary, rule-based fallback

## Context
Hard constraints: no paid AI spend, no local-model ops. v1 read this as "no model at all" (rule-based only). User feedback corrects the product reading: the idea→strategy→analysis loop needs live language understanding to feel alive, and a user-supplied free-tier Gemini key (Flash, Pro opt-in) satisfies the constraints without weakening the architecture.

## Options
A) Rule-only (v1): zero network, zero key management — but keyword matching cannot paraphrase ideas, compare runs, or diagnose results convincingly. Risks a dead-feeling product.
B) Paid LLM required: best quality, violates the $0 constraint. Rejected.
C) Local model required: violates the no-local-ops constraint, heavy QA matrix. Rejected.
D) **Free-tier cloud BYOK with offline fallback (CHOSEN):** Gemini 2.5 Flash default (+ Pro per-call opt-in), user-supplied key in OS keyring, token budgets + caching + quota→fallback, identical validation/confirm pipeline as rule-based.

## Decision
**D.** `AIAssistant` port with two providers: `GeminiAssistant` (primary when key + quota allow) and `RuleBasedAssistant` (always-available fallback/offline). Structured JSON output, context packing budgets, response caching by content hash, mandatory provider/model/token footer, audit logging without secrets. Full contract: `docs/ai-assistant.md`.

## Consequences
+ Conversational quality where it matters (paraphrase, modify, explain, compare) at $0 with user-controlled quota; offline determinism preserved; vendor swap (Anthropic/OpenAI/local) later touches only `alphalab_ai/`, never core.
− Key onboarding friction (paste key), free-tier quota/latency variability, prompt-QA burden. Mitigated by fallback grace, caching, budgets, and replay-based CI (no live key in tests).
− Privacy posture must be explicit: aggregates/specs only, never raw bars; documented in settings screen copy.
