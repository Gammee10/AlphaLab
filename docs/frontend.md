# Frontend

## Role

Research workflow UI. Renders authoritative server data; computes nothing authoritative (local math limited to formatting, chart scaling, diff display).

## Screens (MVP, in loop order)

1. **Strategies** — list + template gallery (param form rendered from the template's JSON Schema; preview text comes from `GET /api/templates` `describe()` — the web never constructs specs client-side beyond form binding).
2. **Strategy detail** — current spec rendered as human-readable rules + version timeline (hash, provenance, diff vs previous) + Edit (form → new version, never in-place).
3. **Backtest launcher** — dataset picker (with manifest/gaps shown), period, capital, costs (preset defaults, editable), sync/async auto.
4. **Run view** — metrics cards (with N prominent; nulls shown as "— (n<30)" etc.), equity + drawdown charts, monthly table, trades table (paginated), assumptions + warnings panel (always visible, not a tooltip footnote). A persistent research-integrity banner sits above results on every run/compare view: "Historical simulation ≠ future performance. MaxDD and Sharpe are in-sample descriptions, not guarantees." (Brief §13; copy is normative — do not soften it.)
5. **Compare** — experiment view: what-changed diff + metric deltas + overlaid normalized equity.
6. **AI panel** — intent box → proposal preview (ops listed, no auto-apply) → Confirm/Reject; Explain and Summarize tabs with cited metric ids.

## API interaction

TanStack Query over `/api/*`; SSE for job progress with polling fallback; Vite proxy `/api → localhost:4100` in dev. All numbers displayed carry `runId + resultHash (short)` in a footer ("this view = run `a3f9…`, engine/1.0") so screenshots are auditable.

## Non-goals

No drag-and-drop strategy builder, no in-browser backtesting, no chart drawing tools, no dark-pool of settings hiding costs. Clarity over visual complexity.
