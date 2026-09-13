# TradingView → Paper Trading Integration

> **PAPER TRADING ONLY.** TradingView alerts feed the existing paper trading path.
> They can never place a live order. There is no live broker, no live feed, and no
> real-market trade path in this integration. Synthetic test events are labelled
> SYNTHETIC and are never real market trades.

## 1. Architecture

```
TradingView alert ──HTTPS──> POST /webhook/tradingview
                                 │
                                 ▼
                    TradingViewEventGateway
                      • fail-closed config check (NOT_CONFIGURED → 503)
                      • paper-only guard (PAPER_GUARD → 503 if broker live-capable)
                      • auth (header X-QuantLab-Webhook-Token or body secret)
                      • validation (source, symbol, timeframe, direction, timestamp, price)
                      • staleness / future-skew checks
                      • idempotency (event_id seen → DUPLICATE, durable JSONL ledger)
                      • NSE session gate (event_time decides; 24/7 symbols exempt)
                                 │
                                 ▼
              PaperTradingLoop.process_signal   ← SAME path as POST /trading/manual
           (session → health → OMS sizing 2% cash → RiskEngine → validate →
            ExecutionEngine → PaperBroker → Portfolio → Journal)
                                 │
                                 ▼
                 data/webhook/events.jsonl  (durable event ledger)
```

The webhook never invents an execution path. It reuses the authoritative
`PaperTradingLoop.process_signal` — the identical code exercised by the manual
trading endpoint — so all existing safety machinery (session, health, OMS
sizing, RiskEngine kill-switch/limits, ExecutionEngine live-broker guards,
portfolio integrity, journal) applies unchanged.

## 2. Endpoints

| Method | Path               | Purpose                                              | Auth              |
|--------|--------------------|------------------------------------------------------|-------------------|
| POST   | `/webhook/tradingview` | Ingest one TradingView alert (paper)             | webhook secret    |
| GET    | `/webhook/events`  | Query durable event ledger (`limit`, `status` filters) | optional API key  |
| GET    | `/webhook/status`  | Integration status: counts, last event, session, broker capability | optional API key |

Recorded outcomes return **200** even when an event is decided (FILLED,
REJECTED_BY_RISK, DUPLICATE, …) so TradingView does not retry; input errors
return **400** (MALFORMED, FORBIDDEN_SOURCE, STALE, FUTURE, UNKNOWN_SYMBOL,
INVALID_TIMEFRAME, NO_PRICE); misconfiguration returns **503** (NOT_CONFIGURED,
PAPER_GUARD); bad/missing secret returns **401** (UNAUTHENTICATED).

## 3. Configuration (environment only, fail-closed)

| Variable                          | Default        | Meaning                                                       |
|-----------------------------------|----------------|---------------------------------------------------------------|
| `QUANTLAB_WEBHOOK_SECRET`         | *(empty)*      | Shared token; **empty disables the webhook** (503). Required. |
| `QUANTLAB_WEBHOOK_MAX_STALE_SECONDS` | `300`       | Reject alerts older than this (replay protection).            |
| `QUANTLAB_WEBHOOK_FUTURE_SKEW_SECONDS` | `60`       | Reject alerts from the future beyond this skew.               |
| `QUANTLAB_WEBHOOK_CONFIDENCE`     | `0.8`          | Signal confidence attached to the strategy signal.            |
| `QUANTLAB_WEBHOOK_KNOWN_SYMBOLS`  | *(universe)*   | Comma-separated allow-list; empty ⇒ auto universe.            |
| `QUANTLAB_WEBHOOK_24_7_SYMBOLS`   | *(empty)*      | Comma-separated symbols exempt from the NSE session gate.     |
| `QUANTLAB_WEBHOOK_LEDGER_DIR`     | `data/webhook` | Directory for the durable `events.jsonl` ledger.              |

**Never** set `QUANTLAB_WEBHOOK_SECRET` to an empty value in production
config; an empty secret is the documented *off* switch. The secret travels in
the request header `X-QuantLab-Webhook-Token` **or** the JSON body field
`secret` (TradingView cannot set custom headers, so its alerts use the body
field). The webhook additionally refuses to run against any live-capable
broker (503 PAPER_GUARD).

## 4. TradingView alert configuration

1. TradingView alert → **Webhook URL**:
   `https://<your-callable-host>/webhook/tradingview`
2. Message body (JSON). Note TradingView's `{{ }}` placeholders and that the
   payload opens with a single quote — the endpoint parses it as a JSON string
   or object:

```json
{"secret": "<QUANTLAB_WEBHOOK_SECRET>", "event_id": "mine_001", "symbol": "NSE:RELIANCE", "timeframe": "1h", "direction": "long", "timestamp": "{{timenow}}", "price": {{close}}, "source": "tradingview"}
```

Required: `secret`, `symbol`, `timeframe`, `direction`, `timestamp`.
Optional: `event_id` (recommended — enables idempotency), `price`, `source`.

- `symbol`: prefix-stripped (`NSE:`, `BSE:`, `NSEFO:`, `NASDAQ:`,
  `NYSE:`, `BINANCE:`, `CRYPTO:` are removed and matched against the known
  universe).
- `direction`: `long`/`buy`, `short`/`sell`, or `neutral` (no order).
- `timeframe`: `1m 3m 5m 15m 30m 45m 1h 2h 4h 1d 1w 1M`.
- `timestamp`: ISO-8601 or epoch seconds/ms.
- If `event_id` is omitted, a deterministic id is derived from
  `symbol + direction + alert minute`, so repeated firings in the same minute
  collapse into one accepted event.

### Required TradingView configuration checklist

- [ ] Callback URL set to `https://<host>/webhook/tradingview`
- [ ] JSON body includes the `secret` field (matching `QUANTLAB_WEBHOOK_SECRET`)
- [ ] `symbol` matches the configured known universe (or is allow-listed)
- [ ] Alert fired on an NSE trading day within 09:15–15:30 IST — or symbol listed in `QUANTLAB_WEBHOOK_24_7_SYMBOLS`
- [ ] Callback host is publicly reachable from TradingView (HTTPS recommended)

## 5. Paper-only safety guarantees

1. **No live broker**: at startup the gateway checks `loop.broker.live_capable`.
   A live-capable broker → `PAPER_GUARD` 503 before any processing. The
   ExecutionEngine independently refuses live brokers while the system is in
   research mode.
2. **No fabricated market trade**: a closed session rejects the event
   (`REJECTED_OUTSIDE_SESSION`), producing no order, no position, no journal
   entry. Session is decided by the alert's `event_time`, not receive time.
3. **No risk bypass**: signals flow through OMS sizing and `RiskEngine`
   (kill switch, max positions, size, exposure, drawdown, daily loss, leverage).
   Rejections are surfaced as `REJECTED_BY_RISK`.
4. **No broker-facing order creation**: the webhook itself never creates
   broker orders; it calls `process_signal`, the manual path already gated by
   session/health/risk/execution.
5. **Idempotent**: a repeated `event_id` returns `DUPLICATE` (load-bearing
   against TradingView retries), persisted in the ledger across restarts.

## 6. Event lifecycle & observability

Every event is appended to
`<QUANTLAB_WEBHOOK_LEDGER_DIR>/events.jsonl` with `status`, `event_id`,
`symbol`, `direction`, `timestamp`, `session_status`, `order_id` (when filled),
and `reason`. Inspect live state:

```bash
# last 20 events
curl http://localhost:8000/webhook/events
# last FILLED events
curl "http://localhost:8000/webhook/events?limit=5&status=FILLED"
# integration health
curl http://localhost:8000/webhook/status
```

Status values: `NOT_CONFIGURED PAPER_GUARD UNAUTHENTICATED MALFORMED
FORBIDDEN_SOURCE STALE FUTURE UNKNOWN_SYMBOL INVALID_TIMEFRAME DUPLICATE
REJECTED_OUTSIDE_SESSION NEUTRAL NO_PRICE FILLED PARTIAL REJECTED_BY_RISK
SKIPPED FAILED UNKNOWN`.

## 7. Example

```bash
curl -s http://localhost:8000/webhook/tradingview \
  -H "Content-Type: application/json" \
  -H "X-QuantLab-Webhook-Token: <QUANTLAB_WEBHOOK_SECRET>" \
  -d '{"event_id":"demo-1","symbol":"RELIANCE","timeframe":"1h","direction":"long","timestamp":'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"',"price":2950,"source":"tradingview"}'
```

## 8. Failure handling / troubleshooting

| Symptom                          | Meaning & fix                                                       |
|----------------------------------|---------------------------------------------------------------------|
| `503 NOT_CONFIGURED`             | Secret unset. Set `QUANTLAB_WEBHOOK_SECRET`.                       |
| `503 PAPER_GUARD`                | A live-capable broker is attached. Reduce risk config to paper.    |
| `401 UNAUTHENTICATED`            | Token/secret mismatch.                                             |
| `400 STALE` / `FUTURE`           | Alert time outside skew window. Check the alert `timestamp`.       |
| `400 UNKNOWN_SYMBOL`             | Symbol outside universe/allow-list. Normalize prefix.              |
| `400 REJECTED_OUTSIDE_SESSION`   | 200 response, event logged — market closed. Nothing was traded.    |
| `DUPLICATE`                      | Event already processed (200) — expected on TradingView retries.   |
| Broker/DB unavailable            | `FAILED`/`UNKNOWN`, fail-closed, no position opened.               |

## 9. Related files

- `packages/webhook/tradingview.py` — ingestion gateway (validation, auth,
  idempotency, session gate, paper-loop routing, ledger).
- `services/api/router_webhook.py` — FastAPI routes.
- `services/api/main.py` — router registration in `create_app()`.
- `tests/unit/test_tradingview_webhook.py` — synthetic + failure suite.
- `reports/TRADINGVIEW_AUDIT_2026-09.md`, `reports/TRADINGVIEW_PAPER_INTEGRATION_2026-09.md`.