# Changelog — QuantLab AI

All notable changes to this project will be documented in this file.

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
