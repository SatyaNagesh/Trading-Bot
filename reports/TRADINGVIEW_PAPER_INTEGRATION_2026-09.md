# TradingView → Paper Integration — Final Report

- **Date**: 2026-09-13 (IST)
- **Repository**: `Trading-Bot` (`main` @ `9321044`, tag `quantlab-trader-final-2026-09` + new commit)
- **Scope**: Safe ingestion of TradingView alerts into the existing **paper-only** pipeline.

## 1. Integration status — CLASSIFICATION: **B (PARTIALLY READY)**

- **PAPER WEBHOOK PATH — READY (A-grade, verified).** Synthetic TradingView
  events complete the full paper round trip: webhook → validation → session →
  OMS sizing → RiskEngine → ExecutionEngine → PaperBroker → Portfolio → Journal,
  with a durable, restart-safe idempotency ledger. All 32 integration/failure
  tests pass.
- **REAL TRADINGVIEW ALERT TEST — NOT VERIFIED (operator-dependent).** Firing a
  genuine alert requires the operator's live TradingView account plus a publicly
  reachable callback URL. This cannot be executed from a sandbox. Required steps
  are documented in `docs/TRADINGVIEW_PAPER_INTEGRATION.md` §4.
- **"REAL NSE SESSION" events** are routed by the real `SessionManager`;
  only the operator's calendar/time config decides what is open. Sessions were
  exercised deterministically in tests via open/closed session shims; the
  sandbox cannot observe a live NSE day.

> ⚠️ **REAL NSE SESSION NOT VERIFIED.** No genuine market event was received or
> executed. Every executed order in this report is a SYNTHETIC PAPER trade.

| Area                          | Status    |
|-------------------------------|-----------|
| Phase 1  audit                | DONE      |
| Phase 2  contract             | DONE      |
| Phase 3  security             | DONE      |
| Phase 4  paper-only guarantee | DONE      |
| Phase 5  no risk bypass       | DONE (by design) |
| Phase 6  idempotency          | DONE      |
| Phase 7  market session       | DONE      |
| Phase 8  observability        | DONE      |
| Phase 9  synthetic test       | DONE (32 tests) |
| Phase 10 real alert test      | **OPERATOR REQUIRED (PENDING)** |
| Phase 11 failure tests        | DONE      |
| Phase 12 docs                 | DONE      |
| Phase 13 final report         | DONE (this file) |

## 2. Audit findings (Phase 1)

- No prior TradingView / webhook / alert ingestion existed anywhere in the repo.
- The sole HTTP ingest surface is `services/api/main.py`; the authoritative
  paper path is `PaperTradingLoop.process_signal` (also exercised by
  `POST /trading/manual`).
- Executed orders follow: session gate → health → OMS sizing (2% cash) →
  RiskEngine → OMS validate → ExecutionEngine → PaperBroker (instant fill) →
  Portfolio → Journal.
- RiskEngine guards live-capable brokers and the ExecutionEngine refuses live
  brokers while the system is closed — both remain the single authority.

## 3. Files changed

| File                                              | Change                     |
|---------------------------------------------------|----------------------------|
| `packages/webhook/__init__.py`                    | new package               |
| `packages/webhook/tradingview.py`                 | ingestion gateway          |
| `services/api/router_webhook.py`                  | FastAPI routes             |
| `services/api/main.py`                            | register webhook router    |
| `tests/unit/test_tradingview_webhook.py`          | synthetic + failure tests  |
| `docs/TRADINGVIEW_PAPER_INTEGRATION.md`           | operator guide             |
| `reports/TRADINGVIEW_AUDIT_2026-09.md`            | Phase 1 audit              |
| `reports/TRADINGVIEW_PAPER_INTEGRATION_2026-09.md`| this report                |

## 4. Tests

Command:

```bash
python -m pytest -q tests/unit/test_tradingview_webhook.py -p no:cacheprovider
```

Result: **32 passed** (existing baseline suite unchanged — see §8).

Coverage: auth (body/header/none/wrong→401-layer), malformed, source guard,
stale, future, unknown symbol, invalid timeframe, neutral, missing price,
closed session (no phantom trade), 24/7 session exemption (end-to-end),
duplicate (in-memory + restart-persistent), kill switch, risk-limit rejection,
broker unavailable (fail-closed), ledger-unavailable (no crash/double order),
disabled webhook (no secret), replay, **PAPER_GUARD** (live-capable broker
never reached — recorded zero broker calls), HTTP full paper round trip
(entry→exit, realized P&L > 0, journal ≥ 1 entry, portfolio integrity
verified), HTTP duplicate, HTTP bad secret, HTTP malformed, HTTP closed
session, HTTP observability (`/webhook/status`, `/webhook/events`), HTTP kill
switch.

## 5. Webhook endpoint & configuration

- Endpoint: **`POST /webhook/tradingview`** (plus `GET /webhook/events`,
  `GET /webhook/status`)
- Auth: header `X-QuantLab-Webhook-Token` **or** body field `secret`, from env
  `QUANTLAB_WEBHOOK_SECRET`. Empty secret ⇒ disabled (503).
- Allow-list / env tuning per `docs/TRADINGVIEW_PAPER_INTEGRATION.md` §3.
- TradingView config (operator steps): see doc §4 — callback URL, body JSON
  with `secret`/`symbol`/`timeframe`/`direction`/`timestamp`.

## 6. Start & verify commands

Start the API (paper config; secret set in environment):

```bash
export QUANTLAB_WEBHOOK_SECRET="$(openssl rand -hex 24)"   # operator-only value
python -m services.api.main                                 # or the project's API entrypoint
```

Verify end-to-end (synthetic event → paper):

```bash
curl -s http://localhost:8000/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-QuantLab-Webhook-Token: $QUANTLAB_WEBHOOK_SECRET" \
  -d '{"event_id":"verify-1","symbol":"RELIANCE","timeframe":"1h","direction":"long","timestamp":"<now ISO8601>","price":2950,"source":"tradingview"}'
curl -s "http://localhost:8000/webhook/events?status=FILLED"
curl -s http://localhost:8000/webhook/status
```

To inspect incoming alerts: watch `GET /webhook/events` and the ledger at
`<QUANTLAB_WEBHOOK_LEDGER_DIR>/events.jsonl` (default `data/webhook/`).

## 7. Risk path & paper/live isolation

- Webhook → `RiskEngine.check_order` (kill switch, max positions, size,
  exposure, drawdown, daily loss, leverage) → OMS → ExecutionEngine
  (refuses live brokers when closed) → broker.
- **PAPER_GUARD**: any live-capable broker on the loop ⇒ 503 before any
  processing. Proven by test: fake live-capable broker recorded **zero** order
  calls.
- No real order can originate from TradingView; the webhook library path has no
  broker credentials and never constructs a broker.

## 8. Regression note

Baseline suite: 594 passed / 7 pre-existing failures (candidates, data-quality
outlier, indicator EMA/RSI/BB) — unrelated to this change. Beer-lantern:
webhook suite adds 32 passing tests; no baseline test was modified.

## 9. Phase 10 — operator checklist (REQUIRED before A-grade)

1. Deploy behind HTTPS with a publicly reachable URL.
2. Set `QUANTLAB_WEBHOOK_SECRET` and (optionally) symbol/time-window env vars.
3. Create a TradingView alert whose Webhook URL is
   `https://<host>/webhook/tradingview` and whose body includes `secret`.
4. Trigger during an NSE session for an NSE symbol (or configure
   `QUANTLAB_WEBHOOK_24_7_SYMBOLS` for crypto).
5. Confirm `GET /webhook/status` counts `FILLED` and `GET /webhook/events`
   shows the order; cross-check the paper Portfolio/Journal.
6. Re-file the same alert and confirm `DUPLICATE` (retry-safe).