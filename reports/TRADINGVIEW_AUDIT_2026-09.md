# TradingView Paper Integration — Architecture Audit (2026-09)

Status: **Phase 1 of the TradingView paper integration is complete. No
TradingView/webhook/alert integration exists in the repository.**

## What was searched

`tradingview`, `webhook`, `alert`, `signal`, `tv`, `paper`, `broker` across
`packages/`, `services/`, `apps/`, `docs/`, `reports/`, `tests/`.

## Findings

| Question | Answer |
|---|---|
| Does a TradingView webhook endpoint already exist? | **No.** `services/api/` (FastAPI) has no webhook route. No `webhook` token anywhere except a *Discord outgoing notifier* (`DISCORD_WEBHOOK_URL`) and *internal* alert engines (`packages/optimization/alerts.py`, `autonomous/health.py`). |
| Does TradingView data ingestion already exist? | **No.** No TV payload, alert, or stream consumer exists. The only external-data path is the yfinance historical pipeline (`packages/market/`), which is pull-based and unrelated to alerts. |
| Are there duplicate webhook/event paths? | **No.** Exactly one HTTP surface ingests anything: `services/api/main.py`. The other `services/*/main.py` (gateway, strategy, risk, execution, portfolio, mobile, research) are thin stubs with no routes that ingest events; `services/gateway/main.py` is a JWT-auth microservice only. No server-side event ingestion exists anywhere else. |
| Where should TradingView events enter? | They must enter through the **existing strategy → risk → execution → broker → portfolio → journal** path. That path is `PaperTradingLoop.process_signal` (`packages/trading/loop.py`), which is already wired into the API as `bot.loop` and exercised by `POST /trading/manual`. |
| Can TradingView input reach the paper path without a second execution path? | **Yes** — by converting a validated TV event into a `Signal` + `Bar` and calling `bot.loop.process_signal(...)` exactly like `/trading/manual`. No new broker, no new OMS, no new risk engine. |

## The authoritative paper path (already proven, will be reused)

```
TradingView event
 -> [NEW: webhook ingestion/validation layer only]
 -> Signal + Bar
 -> PaperTradingLoop.process_signal
     -> session gate (is_open)
     -> health gate (all_healthy)
     -> OMS.create_order(sizing = 2% cash, price from event)
     -> RiskEngine.check_order  (kill switch, max positions, size, exposure,
                                 drawdown, daily loss, leverage, per-strategy)
     -> OMS.validate
     -> ExecutionEngine.execute (refuses live_capable brokers when live is closed)
     -> broker.place_order (PaperBroker/SimulatedBroker -> paper)
 -> PortfolioEngine.apply_fill -> TradeJournal.record_trade (+ daily loss, integrity)
```

Great, so the insertion point is exactly ONE new ingestion/validation/ledger layer.
Nothing else in the execution chain is duplicated or bypassed.

## Security posture already present

- `services/api`: API-key auth (`Bearer`), per-IP rate limiter (120/min default),
  CORS `*` (local/research only; documented in `docs/SAFETY_AND_LIVE_TRADING.md`).
- Broker gateway: live trading CLOSED by default; `create_broker` requires
  `QUANTLAB_LIVE_TRADING_ENABLED=1` for zerodha/alpaca/angel; `ExecutionEngine`
  refuses live-capable brokers while closed.
- Risk engine: kill switch, max positions/drawdown/daily-loss/leverage/exposure,
  per-strategy allocation.
- Session: evaluated in Asia/Kolkata (NSE 09:15–15:30), weekend/holiday aware.

## Gap to implement (Phases 2–9, 11–12)

1. TradingView webhook contract + ingestion endpoint.
2. Auth: secret token (header or body passphrase), timestamp sanity, replay/dedup.
3. NSE session gate → explicit `REJECTED_OUTSIDE_SESSION` (unless 24/7).
4. Event ledger for traceability + query endpoints.
5. Synthetic integration test + failure suite.
6. Docs + runbook.

With `get_bot_started` the loop used by the webhook is the SAME `bot.loop` that
`/trading/manual` uses, so orders, risk, and journal remain in one place.