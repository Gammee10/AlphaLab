# Security

MVP posture: **localhost single-user research tool**. Threat model is constrained but explicit so later multi-user/auth work doesn't require redesign.

## Boundaries and mitigations

| Threat | Mitigation (MVP) |
|---|---|
| Arbitrary code execution via AI/strategy | No code path exists: strategies are JSON, no `eval`/`new Function`/dynamic import of user strings (ADR 0003). Lint rule bans them. |
| Malicious CSV (formula injection, huge files) | 25MB / 2M-row caps; numbers parsed strictly (no formula eval); stored as REAL, rendered as text (no spreadsheet export with `=` passthrough — prefix `'` if CSV export added). |
| Resource exhaustion (giant backtests, sweep bombs) | Bars ≤ 2M/dataset; sync/async threshold; concurrency 2, queue 20, sweep ≤ 32, 120s timeout; `429` with retry hints. |
| Prompt injection → silently altered strategy | AI allowlisted patch ops + schema validation + `baseSpecHash` match + mandatory user confirm. |
| Data exfiltration to AI vendor | Gemini calls send versioned specs + metric aggregates only — never raw bars/CSV. BYOK key in OS keyring/env, never in DB/logs; prompt/response audit rows store patch/text + token counts, never the key. Settings copy documents this. |
| Gemini key handling | Key read from keyring/`GEMINI_API_KEY` at request time, held in memory only, redaction filter on `key|token|secret|authorization` fields; `ai_proposals`/`ai_traces` schema has no key column by design (migration adding one must fail review). |
| API abuse / CSRF | Localhost bind (`127.0.0.1` only) in MVP; same-origin; no cookies/session to hijack. Future networked mode: token auth + CORS allowlist (fields already reserved). |
| Cross-user data leak | `user_id='local'` on all rows; every repo query filters `user_id`; service-layer helper enforces it so adding auth is a caller change, not a domain change. |
| Secret leakage in logs | The only MVP secret is the optional Gemini key (keyring/env-held, never persisted). Logger redacts `key|token|secret|authorization`-matched fields; review gate: any migration adding a key column to ai_* tables fails. |

## What is intentionally deferred

OAuth/JWT, rate-limit-by-user, encrypted-at-rest, audit retention policy. Each has a reserved seam (user_id, provider config, audit table) so deferral is cheap and explicit — not an oversight.
