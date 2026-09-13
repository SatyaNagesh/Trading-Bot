# QuantLab Trader — TODO Closeout (2026-09)

Every item in the release debt inventory is closed below with its exit
classification (A–F) and resolution.

## Taxonomy

- **A** production-blocking (live safety)
- **B** paper-trading-blocking
- **C** research-only / non-trading-path
- **D** docs-only
- **E** obsolete / stale / deferred
- **F** external / environmental

## Closeout table

| ID | Class | Item | Status | Resolution |
|----|-------|------|--------|------------|
| QLT-001 | B | Session gate UTC-vs-IST | **FIXED** | `session/manager.py` evaluates in Asia/Kolkata; `next_session_start` weekday-skip fixed; tests `test/session_timezone.py` |
| QLT-002 | B | Live broker fail-closed | **FIXED** | `create_broker` + `ExecutionEngine` gate on `QUANTLAB_LIVE_TRADING_ENABLED`; `mode="live"` rejected; zerodha/angel no simulated fills |
| QLT-003 | C | AlpacaBroker.get_historical_data NotImplemented | **DOCUMENTED** | Interface stub; market data flows via data pipeline |
| QLT-004 | C | zerodha/angel get_historical_data NotImplemented | **DOCUMENTED** | Interface stub; fine for paper/research |
| QLT-005 | C | base broker get_open_orders -> [] | **DOCUMENTED** | OMS OrderManager is reconciliation source of truth in paper |
| QLT-006 | E | OMS dead `pass` branches | **FIXED** | Removed; comment documents ownership of fill bookkeeping |
| QLT-007 | E | unused empty `TradingStartRequest` | **FIXED** | Schema removed (no endpoint body uses it) |
| QLT-008 | E | stale `NOISE` filter string | **FIXED** | Filter now drops structlog DEBUG lines (ANSI-stripped) |
| QLT-009 | D | stale README / missing docs/ | **FIXED** | README rewritten; docs/ runbooks created |
| QLT-010 | E | 18 orphan 0-byte root files | **FIXED** | `git rm` (tracked) |
| QLT-011 | C | agents/base no-op think/act | **DOCUMENTED** | Framework scaffold, not in trading path |
| QLT-012 | C | hardcoded nifty50 list in data pipeline | **DOCUMENTED** | Data-fetch convenience; loop is bar-driven |
| QLT-013 | C | IntegratedBot coin-flip default signal | **DOCUMENTED** | Simulation fixture; registry is the only approval authority |
| QLT-014 | C | portfolio cash-shortfall clamp mutates qty | **FIXED** | Warn-log added; remain safe fail-safe |
| QLT-015 | D | RiskConfig percent vs RiskBudget fraction | **DOCUMENTED** | Latent; document unit divergence; no auto-wiring added |
| QLT-016 | D | vestigial AFTERNOON/lunch branch | **FIXED** | Continuous-session rule; enum retained for compat |
| QLT-017 | F | external data / NSE liveness | **DOCUMENTED** | REAL NSE SESSION NOT VERIFIED IN THIS RUN; controlled synthetic E2E used |
| QLT-018 | D | CORS `*` on API | **DOCUMENTED** | Local/research-only; live mode must scope CORS + force auth |
| QLT-019 | C | partial-fill branch theoretical | **DOCUMENTED** | Paper brokers fill fully; branch exercised via OMS tests |

## Exceptions kept open (by design)

- The 7 pre-existing research-module test failures are tracked as environmental
  (F): `test_candidates` x3, `test_data_quality::test_outlier_detection`,
  `test_indicators::{test_ema, test_rsi, test_bb}`. They pre-date this release,
  are unrelated to the trading path, and remain visible (not hidden).

## Program-level closeouts (not revived)

- **COMP3**: program CLOSED, paper gate CLOSED, V1/V2 RETIRED in the registry.
  No V3. No AlphaLedger.
- **autonomous_momentum**: unproven; remains RESEARCH.
- **QuantLab Scout**: spec + scaffold preserved (`packages/discovery/`); runtime
  explicitly NOT implemented in this release.

All inventory items are CLOSED (FIXED or DOCUMENTED). No A-class (production-
blocking) items were found at audit time; live trading is CLOSED.