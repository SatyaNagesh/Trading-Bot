# Changelog — QuantLab AI

All notable changes to this project will be documented in this file.

## [quantlab-trader-final] — 2026-09-13

QuantLab Trader release candidate: engineering-complete, paper-engine-ready,
live-trading CLOSED and fail-closed. Basis: clean `main`, tag
`quantlab-trader-final-2026-09`.

### Added
- **Strategy registry** (`packages/strategies/registry.py`, `data/strategy_registry.json`):
  authoritative, evidence-gated status (RESEARCH / VALIDATED / PAPER_APPROVED /
  LIVE_APPROVED / RETIRED). Unproven strategies remain RESEARCH; COMP3 V1/V2 RETIRED;
  `autonomous_momentum` RESEARCH. Legacy `data/strategies.json` statuses reconciled
  to non-authoritative `research` values.
- **Controlled paper E2E tool** (`packages/tools/paper_e2e_check.py`): deterministic
  synthetic-bar E2E + soak; writes `reports/paper_e2e_check_results.json`.
- **New tests (52)**: `test_session_timezone.py` (IST-correct session regression),
  `test_strategy_registry.py` (honest-status guarantees), `test_trading_loop.py`
  (full signal→fill→journal E2E), `test_live_guard.py` (fail-closed live paths).
- **Docs** (`docs/`): QUANTLAB_TRADER_FINAL_STATE, PAPER_TRADING_RUNBOOK,
  OPERATIONS_RUNBOOK, SAFETY_AND_LIVE_TRADING, RESEARCH_AND_STRATEGY_STATUS.
- **Reports** (`reports/`): QUANTLAB_TRADER_FINAL_AUDIT_2026-09.md,
  QUANTLAB_TRADER_TODO_CLOSEOUT_2026-09.md, `quantlab_trader_debt_inventory.json`,
  `paper_e2e_check_results.json`.

### Fixed
- **Session timezone bug (QLT-001):** session gate now evaluates in Asia/Kolkata.
  Previously a UTC `now.time()` was compared to IST market hours, classifying most
  of the real trading day CLOSED. Also fixed `next_session_start` weekday-skip and
  removed the dead lunch-break branch (QLT-016).
- **Live broker fail-closed (QLT-002):** `create_broker` raises `ConfigurationError`
  for zerodha/alpaca/angel unless `QUANTLAB_LIVE_TRADING_ENABLED=1`; `mode="live"` is
  rejected; unknown modes raise; `ExecutionEngine` refuses live-capable brokers when
  closed; zerodha/angel no longer invent a `FILLED` result when `httpx` is missing.
- **OMS:** removed dead `pass` branches in `transition` (QLT-006).
- **Portfolio:** cash-shortfall clamp now logs a warning (QLT-014).
- **Housekeeping (QLT-007/008/010):** removed unused `TradingStartRequest`, stale
  `StdoutFilter` NOISE string, and 18 orphan 0-byte root files.
- **README rewrite (QLT-009):** accurate layout, honest status, real doc pointers.

### Security
- Live trading remains CLOSED by default; documented fail-closed guards and the
  path to (future, supervised) live enablement in `docs/SAFETY_AND_LIVE_TRADING.md`.

### Notes
- Test baseline: **594 passed / 7 failed** (the 7 are pre-existing research-module
  failures untouched by this release).
- COMP3 program remains CLOSED (paper gate CLOSED); `autonomous_momentum` remains
  unproven (RESEARCH). No strategy is approved for paper or live trading.

## [0.1.0-rc1+api] — 2026-08-15

### Added
- **Phase 5 — REST API** (`services/api/`, 19 files): FastAPI app + WebSocket layer over the existing `IntegratedBot`. Routers: health, trading, orders, portfolio, strategies, analytics, risk, production, alerts, config. API-key auth, structured request-logging middleware, OpenAPI at `/docs`.
- **Phase 5 — Discord bot** (`services/discord_bot/`, 5 files): pure HTTP client over the REST API; slash + prefix commands; requires the API to be running.
- **`DEPLOYMENT_GUIDE_PHASE5.md`** — accurate run/deploy instructions for the API + Discord bot.
- `Makefile`: `run-api` and `run-discord` targets (fixed entrypoint to `services.api.main:app`).

### Fixed
- **Recovery hang (critical):** a bloated `alerts` namespace (4.7M rows) made `RecoverySystem.recover()`
  and `IntegratedBot.start()/stop()` effectively hang (~15s+ timeout). `recover()` is now bounded
  (max 5,000 entries/namespace, meta-namespaces skipped) in `packages/production/recovery.py`.
- **Unbounded alert growth:** added `PersistenceStore.prune_namespace()` retention +
  `IntegratedBot._ALERTS_MAX` (20k) so the alerts namespace cannot balloon again.
- **Route shadowing:** static routes `/orders/open`, `/orders/counts`, `/strategies/lifecycle`
  were shadowed by dynamic `/{order_id}` / `/{strategy_id}` (returned `null`). Ordering fixed in
  `router_orders.py` and `router_strategies.py`.
- **`OrderManager.order_count()`** now returns every order status (zero-filled) for a stable API shape.

### Notes
- Phase 5 API suite: **28 passed** (`tests/api/test_api.py`).
- Engine baseline unchanged: **503 passed / 8 pre-existing known failures** (see `CURRENT_STATUS.md`).

## [0.1.0-rc1] — 2026-07-18

### Added
- **Phase 4 (Hardening)** — Complete architecture-to-release pipeline
  - Architecture audit (circular imports eliminated, import side-effects fixed)
  - Resource report, performance profile, recovery validation, config audit
  - Checkpoint hang fix (exclude ephemeral namespaces, 5000-entry cap)
- **80 new tests** across 4 test files for production subsystem
  - `test_production_persistence.py` (41 tests)
  - `test_production_checkpoint.py` (13 tests)
  - `test_production_recovery.py` (13 tests)
  - `test_pipeline_integration.py` (13 tests)
- **API cleanup** — All `-> dict` → `-> dict[str, Any]`, missing type annotations added
- **`MarketRegime` consolidation** — Single source of truth in `domain/models.py`
- **`AgentError` hierarchy fix** — Now extends `QuantLabError` not `Exception`
- **`__all__` exports** — Added to 11 `__init__.py` files
- **Code quality cleanup** — 284 lint issues resolved to 0 (ruff)
- **Code formatting** — 73 files auto-formatted (ruff format)
- **RC1 handoff report** — Comprehensive documentation suite

### Changed
- `ObservationLoop.run()` is no longer `async` (no awaits inside)
- `OrderManager.create_order()` takes `Decimal | None` not `float | None` for price/stop_price
- `seed_database()` explicitly typed `-> None`
- `StrategyFn` type alias added to `trading/loop.py`
- `except: pass` → `except OSError: pass` (3 occurrences)
- Ambiguous variable `l` renamed to `lifetime`/`low`/`lifecycle` (3 occurrences)
- 16 unused variables removed
- 140 unused imports removed

### Fixed
- Checkpoint stop hang — was reading 2.1M alert entries (240MB); now completes in 28ms
- `loop.py` missing `Any` import (was causing `F821` undefined name)
- `fault_inject.py` missing `Awaitable` import
- `candidates/library.py` undefined `entries` variable (real bug — `to_dicts()` referenced non-existent variable)

### Removed
- 140 unused imports across the codebase
- 16 unused variable assignments
- Duplicate `MarketRegime` enum in `analytics/regime_observer.py`

### Security
- Config audit completed — 12 hardcoded secret patterns identified and documented
- All bare `except` clauses replaced with specific exception types

### Known Issues
- 8 pre-existing test failures (indicators, data quality) — see RC1_HANDOFF_REPORT.md
- mypy strict mode configured but not enforced in CI
- `config.yaml` referenced in code but not present in repository

## [0.1.0-dev] — 2026-07-14

### Added
- Initial implementation of QuantLab AI
- 29 packages with autonomous trading pipeline
- 422 passing tests
- Phase 3 validation tools (validate, benchmark, fault_inject, simulate, config_validate)
- Full specification documents (35 documents in docs/)
