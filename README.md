# QuantLab AI — QuantLab Trader

**AI-augmented quantitative research operating system**, with a hardened,
paper-trading-ready execution engine. This repository is the engineering base
for QuantLab Trader: a real
`signal -> strategy -> risk -> portfolio -> order management -> execution ->
journal` pipeline that runs against a simulated/paper broker. Live trading is
**CLOSED** and guarded fail-closed.

## Honest status

- The live broker path fails closed: `QUANTLAB_LIVE_TRADING_ENABLED` must be
  explicitly `=1` for `create_broker`/execution to reach a real broker.
  Live trading is not enabled in this release.
- No strategy is approved for live or paper trading. `autonomous_momentum` and
  every stdlib candidate remain **RESEARCH**; COMP3 V1/V2 are **RETIRED**.
  Authoritative strategy status lives in `packages/strategies/registry.py`
  (data: `data/strategy_registry.json`).
- COMP3 program CLOSED (paper gate CLOSED; see `reports/COMP3_PROGRAM_CLOSEOUT_2026-09.md`).
- Release classification: **1 — ENGINEERING COMPLETE / PAPER ENGINE READY**.
  Classification 2 (validated strategy) is NOT claimed.

## Layout

```
apps/          — CLI and dashboard entry points
services/      — FastAPI service entrypoints (api, gateway, execution, ...)
packages/      — Shared libraries (the engine)
  trading/     — PaperTradingLoop: end-to-end paper pipeline
  oms/         — Order lifecycle
  execution/   — Execution engine with retries + live guard
  portfolio/   — Cash/position/PnL accounting + integrity checks
  risk/        — Pre-trade risk engine (all orders gated)
  session/     — Exchange-local (Asia/Kolkata) trading session gate
  broker/      — Broker abstraction; PaperBroker, SimulatedBroker, live stubs
  journal/     — Trade journal
  health/      — System health monitor (fails trading on anomalies)
  strategies/  — Strategy registry (authoritative status) + research candidates
  research/    — Historical research evidence (incl. COMP3 verification)
  discovery/   — QuantLab Scout scaffold (NOT implemented)
tests/         — pytest suite
docs/          — Operational runbooks + final state (see Documentation)
reports/       — Audit and program reports (research evidence preserved)
data/          — Ignored runtime data (sqlite, caches, holdout corpora)
```

## Quick start

```bash
# Prerequisites: Python 3.13+, Poetry

poetry install

# Run the full test suite
poetry run pytest -q

# Verified release tests
poetry run pytest tests/unit/test_session_timezone.py \
  tests/unit/test_strategy_registry.py tests/unit/test_trading_loop.py \
  tests/unit/test_live_guard.py tests/unit/test_gate4.py

# Controlled paper E2E check + soak (deterministic synthetic bars)
poetry run python packages/tools/paper_e2e_check.py

# API server (paper/research control plane)
poetry run uvicorn services.api.main:app --reload --port 8000
```

## Documentation

Runbooks (see `docs/`):

- `QUANTLAB_TRADER_FINAL_STATE.md` — what this release is and is not
- `PAPER_TRADING_RUNBOOK.md` — how to run the paper engine
- `OPERATIONS_RUNBOOK.md` — daily operations, observability, checks
- `SAFETY_AND_LIVE_TRADING.md` — fail-closed rules; how live trading would be enabled
- `RESEARCH_AND_STRATEGY_STATUS.md` — authoritative strategy status truth table

Key reports (see `reports/`):

- `QUANTLAB_TRADER_FINAL_AUDIT_2026-09.md` — full audit (this release)
- `QUANTLAB_TRADER_TODO_CLOSEOUT_2026-09.md` — exit-taxonomy closeout
- `quantlab_trader_debt_inventory.json` — machine-readable debt inventory
- `COMP3_PROGRAM_CLOSEOUT_2026-09.md` — COMP3 program close-out (evidence preserved)

## License

MIT