# QuantLab Trader — Final Audit (2026-09)

- **Release:** `quantlab-trader-final-2026-09` (see `CHANGELOG.md`)
- **Date:** 2026-09-13
- **Basis:** clean `main` at the release commit (see `git log --oneline -1`)
- **Classification:** **1 — ENGINEERING COMPLETE / PAPER ENGINE READY**

## A. Scope

Audit of the QuantLab Trader: signal -> strategy -> risk -> portfolio -> OMS ->
execution -> journal pipeline, broker layer, session gate, safety posture, and
release documentation. In scope: engineering hardening, tests, fail-closed
verification, strategy-status honesty, paper-trading readiness. Out of scope:
QuantLab Scout implementation, new alpha search, ANY live trading, and reviving
COMP3.

## B. Repository findings at audit start

- Working tree was clean on `main`; `origin/main` tracking present.
- README and several top-level docs contained stale claims (a `docs/` directory
  that did not exist, "35 specification documents", non-existent entrypoints).
- 18 orphan 0-byte files at repo root.
- Focused-engine code was real and functional (PaperTradingLoop, OMS, execution,
  portfolio, risk, broker, journal, health, session), not stubs.
- Research/orchestration plane (`IntegratedBot`) uses an explicitly simulated
  default signal (close-parity LONG/SHORT fixture).

## C. Defect inventory

Machine-readable: `reports/quantlab_trader_debt_inventory.json` (19 items,
classified A–F).

| Class | Meaning | Count |
|---|---|---|
| A | production-blocking (live safety) | 0 |
| B | paper-trading-blocking | 2 |
| C | research-only / non-trading-path | 7 |
| D | docs-only | 3 |
| E | obsolete / stale / deferred | 5 |
| F | external / environmental | 1 |

Fixes applied in this release: QLT-001, QLT-002, QLT-006, QLT-007, QLT-008,
QLT-009, QLT-010, QLT-014, QLT-016 (see closeout report for per-item status).

## D. Paper-blocking fixes

### D.1 Session timezone (QLT-001 — FIXED)
The session gate compared the caller's UTC wall-clock against Asia/Kolkata
market hours. At 09:30 IST (04:00 UTC) the loop classified the market CLOSED,
which would block real-hours paper trading. `packages/session/manager.py` now
evaluates in the calendar timezone (zoneinfo, UTC+05:30 fallback). Regressions
covered by `tests/unit/test_session_timezone.py` (17 tests). Also fixed the
`next_session_start` weekday-skip edge and removed the dead lunch branch.

### D.2 Live fail-closed (QLT-002 — FIXED)
Real-broker classes (`ZerodhaBroker`, `AngelOneBroker`, `AlpacaBroker`) were
instantiable and could place real orders once credentials existed; the
`mode="live"` fallback silently routed to SimulatedBroker; the `httpx`-missing
path reported a simulated FILL. Now:
- `create_broker` raises `ConfigurationError` for zerodha/alpaca/angel unless
  `QUANTLAB_LIVE_TRADING_ENABLED=1`; `mode="live"` is rejected; unknown modes raise.
- `ExecutionEngine.execute` refuses live-capable brokers when the gate is closed.
- zerodha/angel raise `BrokerError` instead of simulating fills when `httpx` is
  unavailable.
Covered by `tests/unit/test_live_guard.py` (14 tests).

## E. Strategy-status honesty (registry)

`packages/strategies/registry.py` + `data/strategy_registry.json` is the
authoritative source. Transition graph + evidence-gated approvals prevent any
unproven strategy from reaching PAPER/LIVE. Ground truth:
- `autonomous_momentum` → RESEARCH (no gate decision ever recorded)
- `sma_crossover` / `ema_trend` / `rsi_mean_reversion` → RESEARCH
- `COMP3_STRATEGY_V1` / `COMP3_STRATEGY_V2` → RETIRED (program closed, paper gate CLOSED)
- `paper-reversal` / `default` → RESEARCH (simulation fixtures)

Legacy `data/strategies.json` statuses reconciled to non-authoritative
`research` values with a pointer to the authoritative registry. Tests 52 come
from `tests/unit/test_strategy_registry.py`.

## F. Safety posture

- Live trading CLOSED; `QUANTLAB_LIVE_TRADING_ENABLED=1` is the single switch.
- Kill switch, health-pause, risk gates, integrity verification in the loop.
- API control plane: API-key auth + rate limiter; CORS `*` is documented as
  local/research-only (see `docs/SAFETY_AND_LIVE_TRADING.md`).
- No secrets in the tree.

## G. Test matrix

```
Baseline (unchanged, pre-existing):  542 passed /  7 failed
  + new release tests:                 52 passed
Release total:                       594 passed /  7 failed
```

The 7 failures are pre-existing research-module issues untouched by this
release: `test_candidates.py` (x3), `test_data_quality.py::test_outlier_detection`,
`test_indicators.py::{test_ema, test_rsi, test_bb}`.

Release-critical suites (must stay green):
`test_gate4.py`, `test_session_timezone.py`, `test_strategy_registry.py`,
`test_trading_loop.py`, `test_live_guard.py`.

## H. Controlled paper E2E + soak

`packages/tools/paper_e2e_check.py` (deterministic synthetic NSE-style bars):

- 3 symbols x 60 bars → **180 signals, 180 fills, 0 rejected, 0 errors, 0 skipped**
- Portfolio integrity verified after every leg (nav diff 0.0)
- 106 closed round-trips journaled
- Soak: 2000 cycles in ~5.4s, integrity verified, FILLED only, no stuck orders

Artifact: `reports/paper_e2e_check_results.json`.

## I. Session behavior (verification note)

Instrument-aware session architecture implemented (calendar-scoped timezone,
testable). For genuinely 24/7 instruments a custom calendar is required; NSE
hours are never faked.

## J. External / environmental limits

- **REAL NSE SESSION NOT VERIFIED IN THIS RUN.** Live exchange-hour behavior,
  real broker APIs, and real market data depend on external providers and
  exchange-side liveness; not verifiable in an offline controlled run. All
  verification used labeled synthetic/controlled inputs (QLT-017).

## K. Residual risks / observations

- The paper loop sizes exit chunks at 2% of cash (not position-aware), so a
  SHORT exit may close only part of a position; documented in the paper runbook;
  the E2E tool uses a position-aware signal.
- `RiskConfig` (percent fields) vs `RiskBudget` (fractions) unit divergence is
  latent — no automatic wiring exists; documented (QLT-015).
- Repo-wide ruff baseline (~2465 pre-existing violations) means "0 lint errors"
  claims in older docs were stale; fixed in CURRENT_STATUS.md. New files are clean.
- OMS `get_open_orders` is the paper reconciliation source of truth; broker
  `get_open_orders` stubs return `[]` for simulated brokers (documented QLT-005).

## L. Reproducibility

- All verification artifacts are committed (reports/ JSON + MD).
- The release was produced from a clean `main`; clone-and-verify steps are in
  `docs/OPERATIONS_RUNBOOK.md`.
- COMP3 evidence preserved under `reports/COMP3_PROGRAM_CLOSEOUT_2026-09.md` and
  `packages/research/verify_comp3_program.py`; holdout-5 lock sha preserved.

## M. Release boundaries

- Following explicit instruction, no COMP3 V3, no AlphaLedger, no Scout runtime,
  no news/macro ingestion, no fabricated profitability or market sessions.
- No strategy is approved; "ENGINE READY ≠ STRATEGY EDGE PROVEN".

## N. Sign-off

The release is classified **1 — ENGINEERING COMPLETE / PAPER ENGINE READY**.
It is safe, reproducible, and fully documented; live trading remains closed.