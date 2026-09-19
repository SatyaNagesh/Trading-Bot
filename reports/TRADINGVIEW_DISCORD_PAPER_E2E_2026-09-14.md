# TRADINGVIEW -> DISCORD - PAPER E2E (2026-09-14)

**Classification: B - INFRA READY, REAL TRADINGVIEW EVENT PENDING (operator-gated)**

Paper only. Live hard-blocked. Fail-closed verified at every gate. No genuine TradingView event has been received.

> **Migrated 2026-09-17 (commits 0ad4c8d → 5fe8e6a):** Discord notification transport
> moved from the legacy webhook URL to the **Discord Bot HTTP (REST) API** —
> `QUANTLAB_DISCORD_BOT_TOKEN` + `QUANTLAB_DISCORD_CHANNEL_ID`, gated by
> `QUANTLAB_DISCORD_ENABLED`. Same fail-closed contract: missing/blank token or
> channel ⇒ notifier is a harmless no-op; transport verified, notification-only,
> cannot order. `.env.example` and `render.yaml` now declare the new env NAMES
> (values only in the Render secret store); the legacy
> `QUANTLAB_DISCORD_WEBHOOK_URL` leg is retained in source for rollback only.

## 1. Repo
- Path: `/home/satyanagesh/Trading-Bot` (main)
- Origin: `https://github.com/SatyaNagesh/Trading-Bot.git` (private)
- HEAD: `5fe8e6a feat: migrate discord notifications to discord bot api`
- Clean, default branch, no force-push, no history reset

## 2. API (paper)
- Uvicorn `127.0.0.1:8000` healthy: /health /ready /live all 200
- /webhook/status visible; /webhook/events journal

## 3. Webhook contract (from current source)
- Method/path: POST /webhook/tradingview
- Header name: `X-QuantLab-Webhook-Token` (secret-holder), value must match env secret
- Sources allowed: tradingview only
- Direction: long/buy->LONG, short/sell->SHORT, neutral->NEUTRAL
- Required fields: symbol, timeframe, direction, timestamp (+ event_id string for dedupe)
- IST session 09:15-15:30; outside -> rejected (no phantom trade)
- Dedupe: same event_id replayed -> rejected (no duplicate)

## 4. Fail-closed (verified)
- No secret in env -> webhook 503 NOT_CONFIGURED (refuses, does not silently accept)
- Live trading: hard-blocked (no live broker reachable, paper guard on)
- Discord: Bot API transport verified (204), notification-only, cannot order;
  absent/blank `QUANTLAB_DISCORD_BOT_TOKEN`/`QUANTLAB_DISCORD_CHANNEL_ID` => no-op

## 5. REAL TradingView event: NOT YET RECEIVED - do not fabricate

## 6. Operator gate (only remaining step)
1. Set the webhook secret (env `QUANTLAB_TV_WEBHOOK_SECRET`) in the server environment
2. Configure ONE paper-only TradingView alert for a NSE symbol (e.g. RELIANCE or NIFTY)
3. When the alert fires, reply: "alert fired at <IST>"
Then the full path TradingView -> webhook -> validation -> paper loop -> RiskEngine -> PaperBroker -> Portfolio -> Journal -> Discord -> this report upgrades to **A**.

Do NOT fabricate. Nothing claimed as A without a genuine event.
