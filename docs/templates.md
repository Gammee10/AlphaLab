# Templates

Genuine reusable abstractions, not prompt folders. Each template is code + schema: a versioned parameter schema and a deterministic `instantiate(params) → StrategySpec`.

## Contract every template implements

```python
class StrategyTemplate(Protocol):
    template_id: str; template_version: str; display_name: str; description: str
    param_schema: dict  # canonical JSON Schema fragment; frontend renders the form from it
    def instantiate(self, params: dict) -> StrategySpec: ...   # pure; raises ValidationError
    def describe(self, params: dict) -> str: ...               # human-readable; served via GET /api/templates for preview + AI grounding
```

- Templates immutable: new defaults/ranges/semantics → new `templateVersion` (old versions remain instantiable for reproducibility).
- Instantiation records `templateRef {templateId, templateVersion, params}` on the created `Strategy`; subsequent user/AI edits **detach** the spec (provenance keeps `derivedFromTemplate` but the spec no longer auto-tracks template changes).
- AI modifies specs via `StrategyPatch` ops, never by editing template code.

## MVP template set (4 — covers the brief's core without sprawl)

| templateId v1.0 | Params (with defaults) | Builds |
|---|---|---|
| `trend-pullback` | `fastEma(50), slowEma(200), pullbackEma(20), atrPeriod(14), slAtr(1.5), rr(2), direction(long), session(07–20 UTC), riskPct(0.5)` | EMA trend + pullback entry + ATR stop + RR target |
| `breakout-donchian` | `channel(20), atrPeriod(14), slAtr(1.0), rr(2), direction(both), riskPct(0.5)` | Donchian breakout: close crosses above/below **prior-bar** channel (`offsetBars: 1` — the kernel includes the current bar, which a close can never exceed); ATR stop |
| `mean-reversion-bollinger` | `bbPeriod(20), stdDev(2), rsiPeriod(14), rsiLow(30), rsiHigh(70), slAtr(1.5), rr(1.5), direction(both), riskPct(0.5)` | Close outside BB + RSI extreme; exit RR + opposite signal |
| `momentum-rsi` | `rsiPeriod(14), entry(55), exit(45), atrPeriod(14), slAtr(2), rr(2), direction(both), riskPct(0.5)` | RSI regime filter + continuation entry |

Each template's full param ranges and one canonical instantiation example ship as JSON fixtures (`backend/tests/fixtures/templates/*.json`) — used by engine tests and the web template gallery.

## Lifecycle

```text
gallery → pick template → form (paramSchema-driven) → preview (describe + spec JSON)
  → Create Strategy (stores Strategy + StrategyVersion v1 with templateRef)
  → edit → v2, v3… (detached specs, provenance chain)
  → backtest any version (runs pin the version hash)
```

## Custom strategies

`blank` creation path builds a spec from a guided form (same validation, `templateRef: null`). No template required; custom specs get identical versioning/execution treatment.

## Non-goals (v1)

No user-authored templates, no template marketplace, no template inheritance. Those need a template-permission model the MVP explicitly defers.
