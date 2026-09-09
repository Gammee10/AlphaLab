# Persistence

SQLite (WAL mode), file `data/alphalab.sqlite3`. SQLAlchemy 2 models + Alembic forward-only migrations in `backend/alphalab_store/` (hand-authored DDL, no autogenerate surprises). `Decimal` mapped via scaled-integer/Numeric for money columns; floats only for OHLCV/indicator-adjacent storage with documented precision. Plus `ai_cache(provider, cache_key, payload, tokens, created_at)` for explain/summarize caching and `ai_traces` for prompt/response audit (no key column — see `docs/security.md`).

## Tables (v1)

```sql
strategies(id TEXT PK, user_id TEXT DEFAULT 'local', name TEXT, template_ref TEXT NULL /*json*/,
           current_version_id TEXT, created_at INTEGER, updated_at INTEGER);
strategy_versions(id TEXT PK, strategy_id TEXT, version_number INTEGER, spec TEXT /*canonical json*/,
           spec_hash TEXT UNIQUE, parent_version_id TEXT NULL, provenance TEXT /*json*/, created_at INTEGER);
-- immutability: NO UPDATE/DELETE allowed on strategy_versions (enforced by trigger raising ABORT)

strategy_templates(template_id TEXT, template_version TEXT, definition TEXT /*json*/,
         PRIMARY KEY (template_id, template_version));
-- Registry only: template CODE lives in alphalab_core (source of truth); a migration seeds/updates registry rows to match.
-- Code-table mismatch at boot = fail startup (prevents describing a template the engine can't instantiate).

datasets(id TEXT PK, user_id TEXT DEFAULT 'local', symbol TEXT, timeframe TEXT, bar_count INTEGER,
         start_time INTEGER, end_time INTEGER, bars_hash TEXT UNIQUE, source TEXT /*json*/,
         manifest TEXT /*json*/, created_at INTEGER);
dataset_bars(dataset_id TEXT, open_time INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL,
         PRIMARY KEY (dataset_id, open_time)) WITHOUT ROWID;

backtest_jobs(id TEXT PK, state TEXT, cancel_requested INTEGER DEFAULT 0, progress TEXT /*json*/, error TEXT NULL,
         created_at INTEGER, started_at INTEGER NULL, finished_at INTEGER NULL);
backtest_runs(id TEXT PK, job_id TEXT, strategy_version_id TEXT, dataset_id TEXT,
         spec_hash TEXT, dataset_hash TEXT, config_hash TEXT, result_hash TEXT UNIQUE,
         engine_version TEXT, config TEXT /*json*/, metrics TEXT /*json*/,
         equity_curve TEXT /*json, ≤2000 pts*/, full_resolution_hash TEXT,
         assumptions TEXT /*json[]*/, warnings TEXT /*json*/, created_at INTEGER);
-- immutability trigger on backtest_runs + datasets: updates/deletes abort
trades(id TEXT PK, run_id TEXT, entry_bar INTEGER, exit_bar INTEGER, direction TEXT,
         qty TEXT /*Decimal canonical*/, entry_price TEXT /*Decimal*/, exit_price TEXT /*Decimal*/,
         fees TEXT /*Decimal*/, gross_pnl TEXT /*Decimal*/, net_pnl TEXT /*Decimal*/,
         intended_risk TEXT /*Decimal*/, realized_risk TEXT /*Decimal*/,
         exit_reason TEXT, ambiguous INTEGER, FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
orders(id TEXT PK, run_id TEXT, signal_bar INTEGER, fill_bar INTEGER NULL, kind TEXT, direction TEXT,
         qty TEXT NULL /*Decimal*/, state TEXT, fill_price TEXT NULL /*Decimal*/, fees TEXT NULL /*Decimal*/,
         FOREIGN KEY(run_id) REFERENCES backtest_runs(id));

instrument_meta(symbol TEXT, meta_version TEXT, pip_size TEXT, contract_size TEXT, lot_step TEXT,
         min_qty TEXT, price_decimals INTEGER, PRIMARY KEY (symbol, meta_version));

experiments(id TEXT PK, user_id TEXT DEFAULT 'local', name TEXT, hypothesis TEXT NULL,
         run_ids TEXT /*json[]*/, baseline_run_id TEXT NULL, created_at INTEGER);
ai_proposals(id TEXT PK, status TEXT, input_refs TEXT /*json*/, intent TEXT,
         patch TEXT /*json*/, validation TEXT /*json*/, provider TEXT, model TEXT NULL, tokens INTEGER NULL,
         created_at INTEGER);
ai_traces(id TEXT PK, proposal_id TEXT NULL, provider TEXT, model TEXT NULL, prompt_hash TEXT,
         response_hash TEXT, tokens_in INTEGER, tokens_out INTEGER, created_at INTEGER);
ai_cache(provider TEXT, model TEXT, cache_key TEXT PRIMARY KEY, payload TEXT, tokens INTEGER, created_at INTEGER);
-- cache_key includes provider+model+input content hash: switching models never serves stale prose.
-- No key column exists on any ai_* table by design (see docs/security.md). Money uses TEXT/Decimal, never REAL.
```

Indexes: `dataset_bars(dataset_id, open_time)`, `trades(run_id, exit_bar)`, `backtest_runs(strategy_version_id)`, `backtest_runs(dataset_id)`.

## Hashing

- Canonical JSON: sorted keys, 6-dp numeric rounding for spec/config, UTF-8, `sha256` hex. `specHash`, `configHash`, `barsHash` computed at write; `resultHash` after run.
- Re-running identical inputs is a content-addressable hit opportunity (API may return existing `runId` with `deduped: true` — still a new `job` row for audit).

## Growth discipline

- 2M bars ≈ ~150MB SQLite — acceptable single-file MVP. Beyond that: shard by dataset file + keep index in SQLite (migration path documented, not built).
- `VACUUM` on dataset delete (datasets deletable only if zero referencing runs; runs themselves never deleted except explicit user purge with confirmation).
