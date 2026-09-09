# Market data

## MVP scope (focused, honest)

- **Instruments:** `EURUSD, GBPUSD` (FX spot), `XAUUSD` (spot metal), `BTCUSD` (spot crypto). No equities in MVP (corporate actions/dividends/splits deferred — FX/crypto/metal have none, which removes a whole error class).
- **Timeframes:** `M5, M15, H1, H4, D1` as **independent datasets** — no resampling engine in MVP. A "timeframe comparison" is N runs over N datasets, explicitly labeled.
- **Sources in MVP:** (1) user CSV import, (2) bundled samples in `data/samples/`, (3) deterministic synthetic generator (seeded, for tests/demos). **No live provider fetching in MVP.** A `MarketDataProvider` port exists so Binance/Dukascopy/OANDA adapters can be added later without touching the engine.

## Canonical bar

```ts
type Bar = { symbol: string; timeframe: Timeframe; openTime: number; /* UTC ms, bar open */
             open: number; high: number; low: number; close: number; volume: number };
```

Rules: `openTime` aligned to timeframe grid — M5/M15/M30 minutes modulo; H1 top of hour; **H4 at 00/04/08/12/16/20 UTC; D1 at 00:00 UTC**; `high ≥ max(open,close)`, `low ≤ min(open,close)`; prices > 0 finite; `volume ≥ 0`. Violations → row rejected with reason (import report), never auto-"fixed". **Dedupe rule: same (dataset, openTime) twice → keep the FIRST occurrence, drop later ones, count in `duplicatesDropped`** (deterministic; re-imports hash identically).

## CSV import format (v1)

```csv
open_time,open,high,low,close,volume
2020-01-02T00:00:00Z,1.12120,1.12200,1.12080,1.12170,0
```

- `open_time` ISO-8601 UTC (offset accepted, normalized to UTC ms); numeric OHLCV; header required; ≤ 2M rows/file; UTF-8.
- Pipeline: `parse → normalize (tz→UTC, sort, dedupe) → validate (range/order/grid) → gap-scan → store → hash`.
- Result: `DatasetManifest { rowsReceived, rowsStored, duplicatesDropped, rowsRejected[], gaps[{from,to,missingBars}], barsHash }` — shown in UI and stored on the dataset so "why are there 40 missing H1 bars in Dec 2021?" is answerable.

## Sessions, timezones, gaps

- Engine/sim time is **UTC only**. Session filter (`startHourUtc/endHourUtc`) applies to signal-bar `openTime` hour. DST irrelevance is a feature: strategies defined in UTC, UI optionally shows a second tz label (display-only).
- Gaps: missing bars are **absent**, not forward-filled. Signals/indicators pause across gaps (`indicators frozen`, `warmup` not faked). Runs record `gapsEncountered`. Weekend FX gaps are normal data, not errors.
- Zero-volume FX rows are legal (volume informational for FX/CFD in MVP).

## Default cost presets (starting points, stored per run, user-overridable)

| Symbol | spreadBps default | notes |
|---|---|---|
| EURUSD | 15 | ~1.5 pips typical retail |
| GBPUSD | 20 | |
| XAUUSD | 25 | metal markup wider |
| BTCUSD | 5 + commission option | exchange-fee model via `commissionPerUnit` |

Presets are UI defaults only — the run's actual values are what count (reproducibility rule).

## Versioning and provenance

`barsHash = sha256(canonical bars)`; `datasetId` immutable once created. Re-import of the same file with one corrected row → **new dataset**, old datasets and their runs untouched. Provider data (future) records `provider, pulledAt, licenseNote`.

## Licensing note

Bundled samples are synthetic or explicitly licensed (generated seeds in-repo). User-imported data is the user's responsibility; the import screen states this. No redistribution of vendor data.

## Synthetic generator (tests + onboarding)

`generate_synthetic({seed, bars, start, volatility, trend})` — Python `random.Random(seed)` GBM-ish walk quantized to instrument pip sizes, volume synthesized as constant 0 for FX (informational) / pseudo-random for BTC. Used for: engine unit tests (known-answer fixtures are hand-written, not generated), empty-data/single-bar/gap edge tests, and a one-click demo dataset so the app works offline on first launch.
