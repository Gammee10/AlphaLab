# API, jobs, errors

Base: `http://localhost:4100`. JSON only. All mutating strategy/AI-confirm routes create new versions (never update). Auth MVP: none (localhost bind); every row carries reserved `user_id = 'local'`.

## REST contracts (v1)

```text
GET    /api/templates                     → { templates: [{ templateId, templateVersion, displayName, description, paramSchema }] }
POST   /api/strategies { name, templateId?, params? } → { strategy }            # v1 created
GET    /api/strategies                    → { strategies }
GET    /api/strategies/:id                → { strategy, versions: StrategyVersion[] }
POST   /api/strategies/:id/versions { spec } → { version }                      # full-spec edit path (validated)
GET    /api/versions/:versionId           → { version }

POST   /api/datasets/import { csvText | file } → { dataset, manifest }          # ≤2M rows, ≤25MB
GET    /api/datasets                      → { datasets }
GET    /api/datasets/:id                  → { dataset, manifest, sample: Bar[0..100] }

POST   /api/backtests { strategyVersionId, datasetId, config } → 200 { run } | 202 { job }
GET    /api/backtests/:runId              → { run }                             # run includes metrics + paginated trades?trades inlined ≤5k else ?page
GET    /api/jobs/:jobId                   → { job }
DELETE /api/jobs/:jobId                   → { job }                             # cancel queued|running
GET    /api/jobs/:jobId/events            → SSE: progress|completed|failed      # Content-Type: text/event-stream

POST   /api/experiments { name, runIds, baselineRunId?, hypothesis? } → { experiment }
GET    /api/experiments/:id               → { experiment, runs: RunSummary[], diff, deltas }
POST   /api/experiments/sweep { strategyId, baseSpec, sweepParams, datasetIds, baseConfig } → { experiment, runIds, failures }  # ≤32 combos; per-combo failures isolated, experiment groups successes only

POST   /api/ai/propose { strategyVersionId?, runIds?, intent } → { proposal }   # AI patch, unconfirmed; response includes provider/model/tokens
POST   /api/ai/confirm { proposalId }      → { version }                        # validates patch → new StrategyVersion
POST   /api/ai/explain { strategyVersionId } → { text, citations, provider, model, tokens }
POST   /api/ai/summarize { runIds }        → { text, citations, provider, model, tokens }
GET    /api/ai/status                      → { provider: gemini|ruled, keyConfigured: bool, quota: { remainingToday } }
```

`BacktestConfig` (request part):
```json
{ "startTime": 1577836800000, "endTime": 1735689600000, "initialCapital": 10000,
  "costs": { "spreadBps": 15, "slippageBps": 5, "commissionPerUnit": 0 },
  "inSample": null, "outOfSample": null }
```
(`instrumentMetaVersion` and `engineVersion` are server-resolved and echoed back — clients don't invent them. No `riskOverride`, no engine `seed` — see `docs/domain-model.md`.)

## Sync vs async rule

- Estimate `barsInRange`; if `< 200k` → execute inline, `200 { run }`.
- Else `202 { job }` + SSE progress every ~500ms (`{ barsProcessed, barTotal, pct }`), polling fallback `GET /api/jobs/:jobId`.
- Concurrency 2, queue 20, sweep ≤ 32 runs, per-run timeout 120s, payload caps above. Exceeding → `429 RATE_LIMITED` with `retryAfterMs`.
- **Idempotency + race safety:** `POST /api/backtests` carries an optional `Idempotency-Key`; the content-addressable dedupe key `(specHash, datasetHash, configHash, engineVersion, instrumentMetaVersion)` means resubmission returns the existing `runId` with `deduped: true`. Concurrent duplicate submissions race on the `UNIQUE(result_hash)` insert: the loser catches the integrity error, re-reads the winner's row, and returns it with `deduped: true` — never a 500, never two runs with the same result hash. A fresh `job` row is still written for audit.
- **Execution hosts:** sync runs execute in FastAPI's threadpool (sync `def` handlers — the event loop is never blocked); async runs execute in a `ProcessPoolExecutor(max_workers=2)` with DB-polled cancel flags and process-kill timeouts (`docs/backtest-engine.md §10`).
- **Atomicity:** a run (run row + trades + orders + metrics + equity) is written in ONE SQLite transaction — a crash or killed worker mid-write leaves zero run rows, never a partial run. Startup recovery marks jobs stuck in `running` as `failed { reason: restarted }`.
- **Cancel:** `DELETE /api/jobs/:jobId` sets `cancel_requested` in the DB; the worker polls it every 1k bars and finishes cooperatively as `cancelled`. Cancel on terminal states → `409 JOB_NOT_CANCELLABLE`. Closing the browser changes nothing server-side (jobs continue; results await polling).

## Error model (typed, stable codes)

```json
{ "code": "STRATEGY_INVALID", "message": "entry.conditions[0]: unknown indicator ref 'ema999'", "details": {} }
```

Codes: `VALIDATION_ERROR, STRATEGY_INVALID, NOT_SUPPORTED_IN_MVP, DATASET_INVALID, DATA_NOT_ORDERED, LOOKAHEAD_OFFSET_REJECTED, INSUFFICIENT_DATA, TOO_MANY_TRADES, JOB_NOT_FOUND, JOB_NOT_CANCELLABLE, RATE_LIMITED, AI_VALIDATION_FAILED, AI_NOT_CONFIGURED, AI_QUOTA_EXHAUSTED, STALE_PATCH, NOT_FOUND, INTERNAL`. HTTP mapping: 400 validation/domain, 404 missing, 409 conflict, 429 limits/quota, 500 internal (logged, no stack to client). Quota exhaustion auto-falls-back to the ruled provider for that call (response carries `provider: ruled, fallbackReason: quota`) rather than failing the UX, unless the caller passes `strictProvider: gemini`.

## Pagination / size discipline

- `GET run` inlines `trades` ≤ 5000; larger → `trades: { total, page, pageSize, url }` with `GET /api/backtests/:runId/trades?page=`.
- Equity curve always downsampled server-side (≤ 2000 pts).
- CSV import rejects `> 25MB` with actionable guidance (split by year/symbol).
