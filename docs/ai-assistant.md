# AI assistant boundary (v2 — free-tier Gemini primary, rule-based fallback)

## Principle (unchanged, now load-bearing)

AI proposes, explains, summarizes. It never executes, never computes money, never writes directly to versions or runs. Every AI output is validated data subject to user confirmation. The deterministic core works fully offline with no key — AI is the experience layer that makes the app feel alive, not a correctness dependency.

```text
User intent ──► AIAssistant ──► StrategyPatch | Explanation | Summary
                      │                      │
                      │                      ▼
                      │            Pydantic validation + grounding check
                      │                      │
                      ├── GeminiAssistant ◄───┴──► RuleBasedAssistant (offline fallback)
                      │  (free-tier, BYOK)        (deterministic, local)
                      └── selection: gemini if key+quota, else ruled (banner discloses which answered)
```

## Why free-tier Gemini (answering the "no model" concern directly)

The v1 architecture chose a rule-only MVP to satisfy "no paid API, no local model" in the strictest reading. Your correction is right: a trading-idea→strategy product without live language understanding feels dead — template keyword matching cannot carry "turn this paragraph into a pullback strategy," "compare these two runs," or "why does high win rate coexist with negative expectancy here?" The revised constraint, matching your stated willingness, is: **no paid dependency, no local-model ops burden — but a user-supplied free-tier cloud key (Gemini 2.5 Flash, with Pro as an opt-in per-call upgrade) is supported, quota-guarded, and gracefully degradable.** This keeps the MVP $0 by default while making the assistant genuinely conversational.

Concretely:
- Default model: `gemini-2.5-flash` — large free-tier quota, fast, sufficient for patch/explain/summarize with packed context. `gemini-2.5-pro` available per-request (summarize/compare only) behind an explicit user toggle + tighter token cap, because Pro's free quota is smaller and slower.
- BYOK: user pastes a Gemini API key in Settings (stored in OS keyring / local env file, never in SQLite rows, never logged). No key → app works fully via `RuleBasedAssistant` with a visible "AI offline — deterministic assistant active" banner. No hard dependency, no paid plan, no vendor lock-in at the domain level.
- If quota exhausts mid-session (`429` / `RESOURCE_EXHAUSTED`), the request degrades to the rule-based provider for that call and says so — never a silent low-quality answer presented as Gemini output.

## Port (implement exactly — both providers conform)

```python
class AIAssistant(Protocol):
    async def propose(self, *, spec: StrategySpec | None, run_ids: list[str], intent: str) -> StrategyPatch: ...
    async def explain(self, *, spec: StrategySpec) -> AssistantText: ...       # {text, citations, provider, model}
    async def summarize(self, *, runs: list[BacktestRunSummary]) -> AssistantText: ...
```

```text
StrategyPatch = { baseSpecHash, ops: PatchOp[], rationale }
PatchOp = setParam | addCondition (optional parentGroupId) | removeCondition | addGroup | addFilter | removeFilter | setRisk | setExits
```

Rules (unchanged, enforced for Gemini output identically): allowlisted target paths; `baseSpecHash` must match current version; no full-spec replacement; max 10 ops per patch, applied atomically in order by a pure `apply_patch(base_spec, ops)` in `alphalab_core` — any op failing validation rejects the whole patch (no partial application); contradictory ops in one patch (e.g. add + remove the same condition id) → reject; every metric cited must be a `metrics.<id>` value present in the input (grounding check → `AI_VALIDATION_FAILED` otherwise); confirm requires explicit user action. Privacy note: user intents may contain personal context ("my $50k account…") — intents are sent to Gemini verbatim when Gemini is the provider; the Settings screen states this and offers the ruled provider for sensitive users.

## Provider 1: GeminiAssistant (primary when configured)

- **Client:** Python `google-generativeai` (or `httpx` REST) confined to `alphalab_ai/gemini.py`. Structured JSON output enforced: `response_mime_type="application/json"` + `response_schema` = the `StrategyPatch` / `AssistantText` schema. Temperature low (0.1–0.2) for patches, 0.4 for prose. Retries: 1 retry on 5xx, none on 4xx except quota→fallback.
- **Context packing (token discipline — this is what makes free-tier viable):**
  - `propose`: current spec JSON (canonical, ~1–2k tokens) + template catalog names/params (not full definitions) + intent (truncated 1000 chars) + allowlisted-path reminder. Never raw bars.
  - `explain`: spec JSON only + template `describe()` string.
  - `summarize`: per-run metric JSON + warnings + trade-count histogram (10 bins), capped at 4 runs/call; larger comparisons chunked with map-reduce summarization.
  - Budgets: propose ≤ 4k in / 2k out; explain ≤ 2k/2k; summarize ≤ 8k/2k. Exceeding → server-side truncation with `truncated: true` flag rather than provider error.
- **Caching:** `explain` cached by `specHash`, `summarize` by `sorted(runIds)+metricsHash` — repeat views cost zero tokens. Cache key includes `provider+model` (switching models never serves stale prose). Cache is in SQLite (`ai_cache`), TTL 30 days.
- **Safety/privacy:** aggregates and specs only; CSV bars never leave the machine; key redaction in logs; prompt/response audit rows (`ai_proposals`, `ai_traces`) store the patch/text + provider/model + token counts, not the key.
- **Failure modes:** `AI_NOT_CONFIGURED` (no key → auto-fallback, not an error surface), `AI_QUOTA_EXHAUSTED` (429 → fallback + banner + `retryAfter`), `AI_VALIDATION_FAILED` (schema/grounding fail → surfaced with the raw error category, raw model text never applied).

## Provider 2: RuleBasedAssistant (fallback + offline guarantee)

Unchanged v1 behavior (keyword→patch map, deterministic spec renderer, metrics renderer with labeled heuristics) — now explicitly the **degraded-mode provider**, not the whole story. Every response carries `{provider: "ruled"}` so the UI banner is honest. It also serves as the test oracle: contract tests assert the Gemini adapter's *validated output shape* matches what the rule-based path produces for the same fixture intents (via recorded/replayed provider in CI — no live key needed).

## Selection & UX contract

```text
Settings has key? ──no──► ruled (+ "connect Gemini free key for NL" hint)
      │ yes
      ▼
quota/token budget ok? ──no──► ruled for this call (+ "Gemini quota paused — deterministic answer" banner)
      │ yes
      ▼
gemini (response footer: "Gemini Flash · 1.2k tokens · grounded in run a3f9…")
```

The footer (provider, model, token count, grounded run/version hashes) is mandatory on every AI surface — it is what keeps "feels alive" compatible with "trustworthy research."

## Config

```text
ai.provider: auto | gemini | ruled   (default auto)
ai.gemini.model_propose: gemini-3.8-flash    # current GA Flash (2026-09); gemini-2.5-flash deprecated for new keys
ai.gemini.model_summarize: gemini-3.8-flash (+ optional pro toggle per call → gemini-pro-latest)
ai.budgets.daily_input_tokens: 200_000 (user-adjustable; hard stop with clear message)
```

## What this does NOT change

Deterministic core isolation, validation-before-confirm, immutability, and the no-code-execution ban are untouched. A Gemini outage, key removal, or quota exhaustion degrades prose quality only — backtests, metrics, and versioning keep working byte-identically.
