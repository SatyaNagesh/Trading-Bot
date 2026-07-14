# RFC-003: Position Sizing Unification

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

Position sizing is defined in two places with overlapping but divergent APIs:

1. **Doc 31 (Strategy Engine)** — `PositionSizer` component with methods like `risk_based`, `fixed_size`
2. **Doc 32 (Risk Engine)** — Section III with Kelly, Fractional Kelly, ATR Sizing, Volatility Targeting, Risk Parity, Equal Weight

The Strategy DSL (doc 31) also defines `risk.*` and `portfolio.*` API functions that duplicate Risk Engine APIs.

## Root Cause

Ambiguous boundary: does position sizing belong to Strategy (sizing is part of strategy definition) or Risk (sizing is a risk control)?

## Resolution

**Position sizing belongs in the Risk Engine** — it is a risk control mechanism, not a strategy definition. Strategy specifies *what* to trade, Risk specifies *how much*.

### New Architecture

```
Strategy Engine               Risk Engine
┌─────────────────┐          ┌──────────────────────┐
│ Strategy DSL     │ ──uses──▶│ PositionSizer        │
│   sizing:        │          │   ├── kelly()        │
│     model: kelly │          │   ├── atr_sizing()   │
│     params: {...}│          │   ├── fixed_size()   │
└─────────────────┘          │   └── risk_parity()  │
                              │                      │
                              │ RiskFilter            │
                              │   ├── pre_trade()    │
                              │   └── post_trade()   │
                              └──────────────────────┘
```

### Interface Contract

```python
# Risk Engine — single source of truth
class PositionSizer:
    async def compute_size(
        self, strategy_id: str, signal: Signal, 
        portfolio: Portfolio, market: MarketContext
    ) -> PositionSize: ...
```

### Strategy DSL simplifies to:

```yaml
sizing:
  model: "kelly"          # References Risk Engine model
  risk_per_trade: 0.01    # Parameter passed to model
  max_position: 0.10
```

No inline sizing logic in Strategy Engine — it delegates to Risk Engine.

### Changes Required

| Document | Change |
|----------|--------|
| doc 31 | Remove `PositionSizer` component, replace with delegation to Risk Engine |
| doc 31 | Remove `risk.*` and `portfolio.*` DSL API definitions |
| doc 32 | Add `PositionSizer` as formal component, consolidate all sizing models |
| doc 35 | Update architecture diagram to show delegation flow |

## Action

- [ ] Move PositionSizer from Strategy Engine to Risk Engine in all docs
- [ ] Clean up Strategy DSL to remove risk/portfolio inline APIs
