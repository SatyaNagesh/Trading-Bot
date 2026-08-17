# Genuine End-to-End Paper-Trading Run — Findings

Date: 2026-08-15 · Mode: paper trading only · Real NSE data via yfinance

## What ran

1. **Real market data**: 250 daily bars each for RELIANCE.NS, TCS.NS, HDFCBANK.NS,
   INFY.NS, SBIN.NS (1250 bars) fetched live and cached at `data/genuine_bars.pkl`.
2. **Real-data research**: `IntegratedBot._run_research(market_bars)` — generated and
   backtested 8 candidate strategies on real bars (~2s). **promoted = 0** (see defect 1).
3. **Genuine paper fills**: 60 real RELIANCE.NS bars driven through the full
   signal → OMS order → risk → execution → fill → portfolio P&L path
   (`paper_trading_run.py`).
4. **Full pipeline simulation**: `bot.run_simulation(days=1)` → 96 cycles, 15 trades.
5. **Persistence**: state verified on disk at `data/genuine_paper.db`
   (alerts/analytics/checkpoints/portfolio/reports/strategies/trades namespaces).

## Genuine results (after fixes)

| Metric | Value |
|---|---|
| Paper signals processed | 60 |
| Fills | 60/60 |
| Journal trades (round-trips) | 35 |
| Realized P&L | **+₹895.33** |
| Final equity | ₹1,000,888 (from ₹1,000,000) |
| Portfolio integrity | **True** |
| Simulation trades | 15 (up from 0 pre-fix) |

### API reflects live trading state (phase 5, clean exit)

The live FastAPI surface was driven with a `TestClient(bot injected)` over a genuinely
running `IntegratedBot`. Every endpoint returned 200 with truthful state:

| Endpoint | Verdict |
|---|---|
| `GET /portfolio/summary` | equity ₹1,001,368.43, realized **+₹1,368.43** (live) |
| `GET /portfolio/positions` | 1 open position |
| `GET /portfolio/integrity` | `verified: True` |
| `GET /portfolio/trades` | 40 persisted trades |
| `GET /orders/counts` | 10 states (all 0 post-clearing) |
| `GET /strategies/lifecycle` | 8 candidates (3 backtesting, 5 validating) |
| `GET /strategies/candidates/rankings` | 8 ranked entries |
| `GET /system/metrics` | counters/gauges/series populated |
| `GET /system/namespaces` | 6 persisted namespaces |
| `POST /trading/cycle` → `GET /trading/status` | cycle 1→**2**, 6 trades via HTTP |
| `WS /ws/dashboard` ping | → `pong` |

## Genuine bugs found & fixed

### Fixed (3) — execution / risk / research-promotion
### Fixed (4) — execution / risk / research-promotion / API cycle

1. **Execution engine double-validation** (`packages/execution/engine.py`).
   `PaperTradingLoop.process_signal` validates an order (CREATED→VALIDATED) and then
   `ExecutionEngine.execute()` called `oms.validate()` again →
   `Invalid transition VALIDATED -> VALIDATED`. Result: **every** paper order failed,
   zero fills, zero trades. Fix: engine only validates when the order is still CREATED.

2. **Risk: max_daily_loss unit mismatch** (`packages/risk/engine.py`).
   `update_daily_loss` accumulates losses in **rupees** (`abs(pnl)`), but
   `_check_daily_loss` compared that rupee figure against a budget `max_daily_loss`
   stored as a **fraction** (0.02 = 2%). Any loss above ~₹2 permanently rejected every
   subsequent order. Fix: normalize the rupee loss against NAV so both sides are
   percentages.

3. **Research could never promote — three stacked defects** (now fixed):
   - `packages/backtesting/engine.py:180` `_check_stops` was a
     `check_stops_not_implemented` stub → positions never exited → **0 trades** in every
     backtest. Implemented real take-profit / stop-loss exits using each template's
     `exit.take_profit_pct` / `stop_loss_pct` (now passed via `Signal.metadata`), plus an
     end-of-run close of any open position.
   - `packages/integration/pipeline.py:525` skipped the `BACKTESTING` lifecycle stage,
     jumping `GENERATING → VALIDATING`. The lifecycle state machine forbids that, so
     promotion crashed once a strategy passed the review gate. Added the missing
     `BACKTESTING` transition.
   - `packages/integration/pipeline.py` jumped `VALIDATING/PAPER_TESTING` straight to
     experiment `PROMOTED`/`ARCHIVED`, which the experiment state machine forbids
     (requires `→ PAPER_TESTING → LEARNING → PROMOTED` and `→ REJECTED → ARCHIVED`).
     Added `Experiment.transition_along()` (BFS over valid transitions) and used it for
     the promote/archive branches.

4. **API `/trading/cycle` was unusable** (`services/api/router_trading.py`).
   The endpoint took `bars_data: dict | None = None` as a bare body param, which FastAPI
   mis-serializes and rejected every payload (422 before any trading ran). The existing
   `CycleRunRequest` / `CycleResultResponse` schemas existed but were never wired in.
   Fix: bound the route to `CycleRunRequest` (field `bars`) + `CycleResultResponse`, and
   relaxed `CycleResultResponse.cycle` from `str` to `int | str` (the engine reports an
   int cycle number). After this, `POST /trading/cycle` executes real cycles: cycle 1→2,
   6 trades, via the HTTP endpoint.

### Verified effect (honest)

After fix 3, backtests on real NSE data now produce **genuine trade volumes and metrics**:

| Strategy | trades | sharpe | ret |
|---|---|---|---|
| sma_10_>_tp2.0_sl1.0 | 368 | −3.22 | −8.3% |
| sma_10_>_tp3.0_sl1.5 | 218 | −1.73 | −5.8% |
| sma_10_>_tp5.0_sl2.0 | 126 | −1.18 | −4.9% |

`promoted = 0` is now the **correct, honest result**: the bot's naive long-only signals
(`close > threshold`, `close < 50`) have genuinely negative Sharpe on real NSE data, so the
pipeline correctly declines them. The promotion pathway itself was proven end-to-end:
a passing strategy drives lifecycle → `PAPER_TRADING` and experiment → `PROMOTED` with no
crashes; losing strategies route VALIDATING → REJECTED → ARCHIVED.

## Human-in-the-loop Trade Advisor (new feature)

`packages/advice/` + `/advice/*` API + Discord button flow — the bot now **asks before it
trades**, and never trades without an explicit Accept:

- **Auto-adopted indicator strategies** (`packages/advice/strategies.py`): SMA golden cross,
  RSI oversold rebound, MACD bullish cross, momentum surge — each emits a bullish setup with
  an **indicator-derived target/expected price** (ATR-based), stop, expected return %, downside
  %, risk/reward and confidence.
- **Bundled NSE company map** (`packages/advice/company_map.py`): symbol → company name + sector
  (no external API).
- **Proposal lifecycle** (`packages/advice/models.py`): `pending → approved | rejected | expired`.
  **Default is NO**: any pending proposal expires after 5 min and is treated as a skip.
- **REST** (`services/api/router_advice.py`): `POST /advice/scan`, `GET /advice/proposals`,
  `POST /advice/proposals/{id}/approve`, `.../cancel`, `POST /advice/reconcile`.
- **Discord** (`services/discord_bot/advice_cog.py`): polls pending proposals, posts the
  analysis embed with **✔ Accept / ✖ Cancel buttons**, executes on click, expires on timeout.

Proven end-to-end (`advice_demo.py`), on real NSE daily bars:

| Step | Result |
|---|---|
| `POST /advice/scan` | 3 proposals (TCS, INFY) with company, current/expected price, +3.8→+4.8%, r/r 1.5, confidence |
| **Approve** TCS | `exec.action=FILLED, side=BUY` — 8 qty @ ₹2361, cash ₹1M→₹981,112, open position=1 |
| **Cancel** INFY | `status=rejected` — **no order placed** |
| No answer | stays `pending`, auto-expires in 5 min (default-NO, verified by unit test) |

Unit tests: `tests/unit/test_advice.py` — 5 passed (approve-executes, cancel-skips,
expired=default-NO, scan-filters). Full suite: **537 passed / 7 pre-existing failures**.

## Genuine defects still open (not fixed — reported as-is)

- **The default research signal function is long-only and threshold-naive** (`close > 0`),
  so it is structurally loss-making on real equities. It is deliberately conservative in the
  bot, but it means strategy *research* will never surface a promotable strategy without a
  better alpha source (e.g. cross, momentum/mean-reversion, regime filters). Not a crash —
  an honest design limitation surfaced by real-data testing.

## Files
- `paper_trading_run.py` — reusable genuine end-to-end harness.
- `genuine_full_run.py` — 5-phase end-to-end harness: research→promote on synthetic
  trending series, genuine paper fills over real NSE bars, integrated `run_cycle`,
  persistence verification, and live API + WebSocket verification. **Clean exit 0.**
- `advice_demo.py` — advisor flow demo (scan → proposal → approve=fill / cancel=no / expire).
- `packages/advice/` — advisor: company_map, models, strategies, advisor.
- `services/api/router_advice.py` — `/advice/*` REST endpoints.
- `services/discord_bot/advice_cog.py` — Discord button-approval flow.
- `data/genuine_bars.pkl` — cached real NSE bars.
- `data/genuine_paper.db` — persisted store from the final run (68 rows across 6 namespaces).
- `GENUINE_RUN_REPORT.md` — this report.

## Commits
- `fd5e133` (prior): Phase 5 blocker fixes, 531-pass suite, unpushed.
- All fixes above (execution, risk, backtest stops, lifecycle, experiment, API cycle,
  portfolio/strategies routers) plus the **Trade Advisor feature** (advice package,
  /advice API, Discord button flow) are **uncommitted** (awaiting approval).
  Suite: 537 passed / 7 pre-existing failures (unchanged set).
