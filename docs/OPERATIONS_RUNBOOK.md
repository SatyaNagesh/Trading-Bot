# Operations Runbook

## Daily checks

1. **Integrity**: every trading session must end with
   `portfolio.verify_integrity()["verified"] == True`. The loop enforces this
   via `HealthMonitor.check_portfolio_integrity` and pauses trading otherwise.
2. **Health**: `loop.health.report()`; any `critical` alert pauses trading.
3. **Risk**: `loop.risk.summary()` — kill switch, rejected orders, daily loss.
4. **Journal**: reconciliation of closed round-trips vs portfolio realized PnL.
5. **Persistence**: the research/control plane persists to `data/quantlab.db`
   via `PersistenceStore`; verify `store.list_namespaces()` after runs.

## Test matrix

```bash
poetry run pytest -q
```

Baseline for this release: **594 passed / 7 failed**. The 7 failures are
pre-existing and unrelated to this release (indicator/data-quality research
modules):
- `tests/unit/test_candidates.py` (x3)
- `tests/unit/test_data_quality.py::test_outlier_detection`
- `tests/unit/test_indicators.py::test_ema`
- `tests/unit/test_indicators.py::test_rsi`
- `tests/unit/test_indicators.py::test_bb`

Release-critical suites (must be green):
```bash
poetry run pytest tests/unit/test_gate4.py \
  tests/unit/test_session_timezone.py \
  tests/unit/test_strategy_registry.py \
  tests/unit/test_trading_loop.py \
  tests/unit/test_live_guard.py
```

## Observability

- Structured logging via `structlog` (configured in `packages/core/logging.py`);
  production format is JSON.
- `HealthMonitor` raises critical alerts on: broker disconnect, missing market
  data, high latency, stale data, API failures, risk-engine unhealthy state,
  portfolio-integrity mismatch, system exceptions.
- `MetricCollector`/`OperationalDashboard` aggregate cycle counters for the
  IntegratedBot research plane.

## Recovery

- `PersistenceStore` + `RecoverySystem` + `Checkpointer` restore trades,
  portfolio, orders, strategies, alerts, scheduler state after restart.
- `IntegratedBot.start()` resumes from the latest checkpoint via
  `recovery.recover()`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| All orders `skipped` | Session gate CLOSED, or `HealthMonitor` trading paused |
| Orders `rejected` | Risk budget exceeded, or kill switch active |
| `ExecutionError` on a live broker | Live trading not enabled (by design) |
| Journal empty after buys | Journal records closed round-trips only |
| High memory | Host limit ~3.7GB; keep bar feeds bounded in memory |