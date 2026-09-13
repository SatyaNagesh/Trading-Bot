# Discord Integration Audit — QuantLab Trader

- **Date**: 2026-09-13
- **Repository**: `Trading-Bot` (`main` @ `23b5c17`)
- **Scope**: Determine whether the current QuantLab Trader runtime is connected to the Discord alert path; identify the historical "Spidey Bot" alert source. **Audit-only — no code changed, no webhook replaced, no strategy reactivated.**

## 1. Headline finding

**Current QuantLab has NO Discord notification/alert integration at all.** There is
no notifier module, no `DISCORD_WEBHOOK_URL` config, and no alert→Discord wiring.
The historical "Spidey Bot" messages (`🔴 SELL RELIANCE`, `Triggered By
bollinger_squeeze`, `strategy vote`, `Multi-Strategy AI`, `1/4 strategies`,
TradingView links) were produced by a **separate, legacy project** — not this
repository.

---

## 2. Event-flow map

**Current QuantLab (this repo):**

```
[run_cycle / research cycle]
   │  (packages/integration/pipeline.py run_cycle)
   ▼
AlertEngine.check_all()           ── degradation / regime / performance alerts
HealthMonitor.recent_alerts()     ── health alerts
Recovery alerts                   ── recovery_failure alerts
   │
   ▼
IntegratedBot.prod.alerts  (in-app namespace store, dashboard)
GET /alerts/, /alerts/counts      ── API only
   │
   ✗ NO SINK  →  no Discord client, no webhook, no outbound notifications
```

Trading-loop events (signals, orders, fills) flow signal → OMS → RiskEngine →
ExecutionEngine → PaperBroker → Portfolio → **Journal** (persistence only). They
have no notification sink either.

**Legacy Spidey Bot (separate project, source of historical messages):**

```
GitHub Actions cron (scheduler)
   ▼
trading-bot/ensemble.py          ── multi-strategy voting ("1/4 strategies",
│                                    "strategy vote"; min 2/4 to fire)
├── strategies/bollinger_squeeze.py  ── "Triggered By bollinger_squeeze"
├── strategies/rsi_reversal.py
   ▼
trading-bot/notify.py            ── Discord rich embeds ("🔴 SELL RELIANCE",
│                                    TradingView link)
trading-bot/run_backtest.py      ── backtest-result embeds
   ▼
Discord webhook ────────────────► Discord channel (receives messages)
```

**Interactive control bot (current repo, separate process — NOT the notifier):**

```
services/discord_bot/ (discord-py, HTTP client to REST API)
   ├── commands.py     ── slash/prefix commands (status, start/stop, portfolio…)
   └── advice_cog.py   ── polls /advice/proposals, posts proposal embeds w/ buttons
   (requires QUANTLAB_DISCORD_TOKEN; never emits strategy/alert notifications)
```

---

## 3. Which system generated the historical Discord message?

Answer: **C — separate / legacy service** (the old "Spidey Bot" trading bot,
not current QuantLab Trader).

Evidence (repo-internal, no guessing):

- The entire `Trading-Bot` repo has **no** `Spidey`, `Multi-Strategy AI`,
  `strategy vote`, `ensemble.py`, or `notify.py` — and **no** Discord webhook
  notifier (verified by search).
- `packages/core/seed.py:24` contains only a seeded **database strategy name**
  `Bollinger Squeeze` (an unrelated echo of the legacy strategy name; it plays no
  role in any notification path and is not reactivated).
- The legacy design + notification template — matching the historical messages
  verbatim (`🟢 BUY … / 🔴 SELL …`, "View on TradingView" link,
  "Multi-strategy voting (min 2/4 to fire signal)", GitHub Actions cron,
  `notify.py` "Discord rich embed sender") — lives in the **Obsidian Notes**
  project file `Projects/AI-Trading-Bot.md` (`/home/satyanagesh/Documents/opencode-discord-bot/work/Notes/Projects/AI-Trading-Bot.md`).
- The legacy notebook `/home/satyanagesh/Documents/opencode-discord-bot/bot.py` is
  a different AI assistant (OpenRouter GPT-4o-mini, reads/edits the Trading-Bot
  repo) — it is not the alert notifier either.

⚠️ Credential note: the legacy `bot.py` contains a plaintext Discord token and an
OpenRouter API key. **Redacted here; reported for cleanup, not reproduced in this
report.**

## 4. Current runtime configuration

| Item                            | State                                                       |
|---------------------------------|-------------------------------------------------------------|
| `DISCORD_WEBHOOK_URL` config    | **Absent** — no field in `packages/core/config.py`; no `DiscordNotifier` module (referenced only in the stale `reports/LEVEL3_SESSION_2026-09-04.md`; code does not exist) |
| `QUANTLAB_DISCORD_TOKEN`        | Not set in any `.env`, not exported; bot refuses to start (`discord_token_missing` per `services/discord_bot/main.py:30`) |
| `.env` files                    | None found in repo or home; no `DISCORD*`/webhook vars exported |
| API / engine process            | **Not running** (nothing on port 8000; no `uvicorn`/`services.api` process) |
| Alert sink                      | In-app `prod.alerts` store + `GET /alerts` API + WebSocket dashboard only |
| Discord-capable code in repo    | `services/discord_bot/` (advice/control only, needs token + running process) |

## 5. Why no new Discord messages

Primary cause (per instruction do-not-guess, verified): **the current QuantLab
architecture has no Discord output path.** The historical sender was a distinct
legacy service that is not part of this repo and is not running here. Secondary
contributors: no runtime process is currently running, and even while running the
current alert engine emits to an in-app store, never to Discord.

## 6. Synthetic test (`QUANTLAB_DISCORD_TEST`)

**BLOCKED BY DESIGN — no current path exists.**

Per the task, the test event must travel the *same* current notification path as
real alerts. That path does not exist in the current architecture (no notifier
module, no webhook config). Per the hard rule ("do not replace the existing
webhook until the current architecture is understood"), I did **not** build a new
notifier, did **not** send anything to Discord, and did **not** fabricate an
alert. The audit completes the diagnosis; a Phase-2 change (below) is required
before a synthetic test is possible.

## 7. Failure-mode review

Trivially satisfied: there is **no Discord dependency** in the current trading
runtime — no notifier module, no config dependency, nothing to fail. Trading and
risk execution are fully independent of Discord. (The separate
`services/discord_bot` control bot *can* invoke `POST /trading/start|stop` as
operator commands — that is control-plane by design and outside the alert path.)

## 8. Current-alert-format recommendation (Phase 2, not yet applied)

When a notifier is built it must label alerts as current-quantlab state:
`QuantLab • PAPER`, session/mode, strategy id, symbol, timestamp (IST), signal,
confidence, risk status, reason, TradingView link if available, and an explicit
`PAPER` marker. It must **not** reuse legacy wording (`Multi-Strategy AI`,
`1/4 strategies`) — that wording described the retired Spidey system.

## 9. Next step (recommended, separate explicit change)

1. Add `DiscordNotifier` (async httpx) reading `DISCORD_WEBHOOK_URL` from env;
   empty URL ⇒ documented no-op (fail-open, non-critical), matching the historical
   module design but re-built for the current pipeline.
2. Hook it to the same lightweight event source already used by the paper loop
   (signal/fill/risk events) — never to strategy logic, never trading-capable.
3. Then run `QUANTLAB_DISCORD_TEST` end-to-end and observe the ledger.
4. Paper/live safety: notifier is read-only, never creates orders, never bypasses
   strategy/risk/execution.

## 10. Classification

**B — DISCORD WORKS BUT CURRENT QUANTLAB IS NOT CONNECTED.**

Discord channel output works (receives messages — historically from the legacy
Spidey project). Current QuantLab has **no** Discord connection by construction.
Contributing structural note: option E (architecture gap) applies in the sense
that the notifier module is missing from the current architecture rather than
mis-configured.

| Classification | Verdict |
|----------------|---------|
| A. Current QuantLab Discord ready | ✗ |
| **B. Discord works, current QuantLab not connected** | **✓ primary** |
| C. Discord config broken | ✗ (no config exists) |
| D. No alertable current events | Partial (alerts exist but unsinked; runtime currently stopped) |
| E. Integration architecture problem | Contributing (notifier module absent) |

## 11. Paper/live safety

Confirmed: no Discord component can place orders in this repo today. Audit
introduces zero execution-path changes. RiskEngine/ExecutionEngine/paper-loop
guards unmodified (`23b5c17` HEAD, clean tree before/after audit).