# QuantLab AI — Phase 5 Deployment Guide

**Version:** 0.1.0-rc1 · **Date:** 2026-08-15
**Scope:** The two Phase 5 services — the **FastAPI REST API** (`services/api/`) and the **Discord bot** (`services/discord_bot/`).

> This guide covers what is actually shipped in Phase 5. For the engine's production-hardening
> checklist (monitoring, broker, rollback), see `DEPLOYMENT_CHECKLIST.md`.

---

## 1. Architecture

```
QuantLab engine (packages/)       -- IntegratedBot: signal → order → risk → execution → portfolio → journal
        ▲ delegates (no logic dup)
        │
QuantLab REST API (services/api/) -- FastAPI + WebSocket, thin wrapper over IntegratedBot
        ▲ httpx client
        │
QuantLab Discord Bot (discord/)   -- slash commands over the REST API
```

- **API** wraps the existing engine. All business logic stays in `packages/`; the API only
  translates HTTP/WS ↔ engine calls.
- **Discord bot** is a pure HTTP client — it does **not** import the engine directly. It requires
  the API to be running.

---

## 2. Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.13+ | Runtime |
| Poetry | latest | Dependencies |
| `discord-py` | 2.7.1+ | Discord bot (`pip install discord-py` or add to `services/discord_bot` deps) |
| `fastapi`, `uvicorn`, `httpx`, `structlog`, `pydantic-settings` | see `services/api/pyproject.toml` | API runtime |

The engine persists to SQLite at `data/quantlab.db` (created automatically, directory auto-made).

---

## 3. Environment (.env)

Copy `.env.example` and set:

| Variable | Required | Notes |
|---|---|---|
| `QUANTLAB_API_HOST` | no | default `0.0.0.0` |
| `QUANTLAB_API_PORT` | no | default `8000` |
| `QUANTLAB_API_API_SECRET` | **yes in prod** | Bearer/API-key secret; default is dev-only |
| `QUANTLAB_API_DB_PATH` | no | default `data/quantlab.db` |
| `QUANTLAB_DISCORD_TOKEN` | yes (Discord) | Bot token from the Discord Developer Portal |
| `QUANTLAB_DISCORD_API_BASE_URL` | no | default `http://localhost:8000` |
| `QUANTLAB_DISCORD_API_SECRET` | yes | must match API secret |
| `QUANTLAB_DISCORD_COMMAND_PREFIX` | no | default `!quantlab` |
| `QUANTLAB_DISCORD_ADMIN_ROLE` | no | default `QuantLab Admin` |

Generate a strong secret:

```bash
openssl rand -hex 32
```

`.env` is gitignored (`chmod 600 .env`).

---

## 4. Run the API

```bash
cd /home/satyanagesh/Trading-Bot

# install deps
poetry install

# start (dev, auto-reload)
make run-api          # == poetry run uvicorn services.api.main:app --reload --port 8000

# or production-style single worker
poetry run uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

### Verify

```bash
curl http://localhost:8000/health        # {"status":"ok","service":"quantlab-api"}
curl http://localhost:8000/live          # {"alive":"true"}
curl http://localhost:8000/ready         # {"ready":..., "database_accessible":...}
curl http://localhost:8000/docs          # OpenAPI / Swagger UI
```

Routes are grouped under `/trading`, `/orders`, `/portfolio`, `/strategies`, `/analytics`,
`/risk`, `/system`, `/alerts`, `/config`, plus `/alerts` and a WebSocket.

---

## 5. Run the Discord bot

The Discord bot talks to the API over HTTP. Start the API first, then:

```bash
# if not installed already
pip install discord-py

# start
make run-discord        # == poetry run python -m services.discord_bot.main
```

Add the bot to a server, grant it message-content and slash-command intents, then use
`!quantlab`-prefixed commands (or the synced slash commands).

> The bot logs `discord_token_missing` and exits if `QUANTLAB_DISCORD_TOKEN` is unset.

---

## 6. Tests

```bash
# Phase 5 (API) suite
PYTHONPATH=. python3 -m pytest tests/api/test_api.py -q        # 28 passed

# Engine + production suite (verify no regressions)
PYTHONPATH=. python3 -m pytest \
  tests/unit/test_production_persistence.py \
  tests/unit/test_production_checkpoint.py \
  tests/unit/test_production_recovery.py \
  tests/unit/test_gate4.py \
  tests/unit/test_pipeline_integration.py -q                   # 173 passed
```

Full engine baseline: `503 passed / 8 known pre-existing failures` (see `CURRENT_STATUS.md`).

---

## 7. Operational notes (Phase 5 hardening)

- **Recovery is bounded.** `RecoverySystem.recover()` caps per-namespace iteration at 5,000
  entries and skips meta-namespaces (`checkpoints`/`plugins`/`metrics`) so a bloated store cannot
  stall a restart.
- **Alert retention.** The engine prunes the `alerts` namespace to the latest 20,000 entries per
  analytics cycle (`IntegratedBot._ALERTS_MAX`), preventing unbounded growth (a prior run reached
  4.7M rows and hung `recover()` / `stop()`).
- **Route ordering.** Static routes (`/orders/open`, `/orders/counts`, `/strategies/lifecycle`)
  are declared before dynamic `/{id}` routes so `{id}` cannot shadow them.

---

## 8. Known limitations / next steps

- ✅ Phase 5 API + Discord bot complete and tested (`28 passed`).
- ✅ Recovery hang and route-shadowing bugs fixed.
- ⏭ Live brokerage adapters exist but are untested — paper trading default.
- ⏭ API auth is API-key-only; no OAuth/RBAC yet.
- ⏭ Full CI/CD pipeline and Docker images are not yet configured (see `DEPLOYMENT_CHECKLIST.md`).