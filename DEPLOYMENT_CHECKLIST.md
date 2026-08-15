# QuantLab AI — Deployment Checklist

> **System:** AI-augmented quantitative research & trading OS  
> **Packages:** 31 shared packages across 7 microservices  
> **Validation Status:** 38/38 E2E · 6/6 fault injection · 8/8 config tests — all passing  
> **Phase 2 Complete:** Orphan removal, config cleanup, integration wiring

---

## 1. Pre-deployment Verification

### 1.1 Test Gates

- [ ] All **38 E2E validation harness stages** pass
  ```bash
  poetry run pytest tests/ -x --tb=short -v | grep "PASSED\|FAILED"
  ```
- [ ] All **6 fault injection tests** pass (`packages/hardening/`, `packages/production/fault.py`)
- [ ] All **8 config validation tests** pass (`tests/unit/test_gate7.py::TestProductionConfig`)
- [ ] No [SKIP] or [xfail] tests in output — every gate must be green
- [ ] Coverage meets threshold: `poetry run pytest --cov-fail-under=50`

### 1.2 Static Analysis

- [ ] Ruff lint passes: `poetry run ruff check .`
- [ ] Ruff format check passes: `poetry run ruff format --check .`
- [ ] MyPy strict passes on `packages/` and `services/`: `poetry run mypy packages/ services/`
- [ ] Pre-commit hooks pass: `poetry run pre-commit run --all-files`

### 1.3 Build & Dependency Audit

- [ ] `poetry check --strict` reports no warnings
- [ ] `poetry show --outdated` reviewed — no unpinned breaking upgrades
- [ ] No dependency conflicts (resolve with `poetry lock --check`)
- [ ] Docker images build clean: `make docker-build`

---

## 2. Environment Setup

### 2.1 Runtime Requirements

- [ ] **Python 3.13+** installed and active: `python --version`
- [ ] **Poetry** installed: `poetry --version`
- [ ] **Docker** and **docker compose** installed: `docker compose version`
- [ ] **kubectl** configured if deploying to Kubernetes
- [ ] **helm** installed if using Helm chart (`deploy/helm/quantlab/`)

### 2.2 Environment Variables (`.env`)
_Copy from `.env.example` and override every placeholder:_

| Variable | Required | Source |
|---|---|---|
| `ENV` | Yes | `production` |
| `DEBUG` | Yes | `false` |
| `LOG_LEVEL` | Yes | `INFO` |
| `SECRET_KEY` | **Critical** | Generate via `openssl rand -hex 32` |
| `POSTGRES_DSN` | Yes | Production DSN with credentials |
| `REDIS_DSN` | Yes | Production Redis URL |
| `QDRANT_URL` | Conditional | Required if knowledge graph enabled |
| `NEO4J_URI` | Conditional | Required if knowledge graph enabled |
| `NEO4J_USER` | Conditional | |
| `NEO4J_PASSWORD` | Conditional | |
| `RABBITMQ_DSN` | Conditional | Required if event bus enabled |
| `MINIO_ENDPOINT` | Conditional | Required if data lake enabled |
| `MINIO_ACCESS_KEY` | Conditional | |
| `MINIO_SECRET_KEY` | Conditional | |
| `API_HOST` | Yes | `0.0.0.0` |
| `API_PORT` | Yes | `443` for production (behind reverse proxy) |
| `DEFAULT_INITIAL_CAPITAL` | Yes | Match your deployment risk policy |

- [ ] `.env` file exists and **is NOT committed** (it's in `.gitignore`)
- [ ] All placeholder values (`change-me-in-production`, `quantlab123`) replaced
- [ ] `ENV=production`, `DEBUG=false`, `LOG_LEVEL=INFO`

### 2.3 Infrastructure Health

- [ ] PostgreSQL 16 reachable: `pg_isready -h <host> -U quantlab`
- [ ] Redis 7 reachable: `redis-cli -h <host> ping`
- [ ] Qdrant API responds: `curl http://<qdrant>:6333/health`
- [ ] Neo4j reachable: `curl http://<neo4j>:7474`
- [ ] RabbitMQ management UI reachable (port 15672)
- [ ] MinIO reachable: `curl http://<minio>:9000/minio/health/live`

---

## 3. Database Initialization

### 3.1 PersistenceStore (SQLite — local/embedded)

- [ ] `data/` directory exists and is writable: `mkdir -p data && touch data/.write-test && rm data/.write-test`
- [ ] Database path matches `config.yaml` (default: `data/quantlab.db`)
- [ ] WAL mode enabled (auto on first `PersistenceStore` init)

### 3.2 PostgreSQL (production multi-node)

- [ ] Alembic migrations up-to-date: `poetry run alembic upgrade head`
- [ ] Alembic history checked: `poetry run alembic history`
- [ ] Connection pool configured for expected concurrency (default: 5)

### 3.3 Schema Verification

- [ ] Verify all 17 `ProductionStore` namespaces exist post-init:
  `experiments, strategies, lifecycle, trades, orders, portfolio, positions, analytics, reports, knowledge, alerts, scheduler, observations, config, checkpoints, plugins, metrics`
- [ ] Indices created correctly (primary key on `namespace + key`)
- [ ] Journal mode = WAL, synchronous = NORMAL

---

## 4. Broker Configuration

### 4.1 Mode Selection

- [ ] **Paper trading**: `BROKER_MODE=paper` — realistic fills, 97% fill probability, 50ms simulated latency
- [ ] **Live trading**: `BROKER_MODE=zerodha|alpaca|angel`

### 4.2 Paper Trading (pre-live validation)

- [ ] `PaperBroker` configured with correct initial capital
- [ ] Position sizing, max positions, symbol universe set in `config.yaml` → `paper_trading` section
- [ ] Risk engine limits confirmed:
  - `max_concurrent_trades` (default 5)
  - `max_position_size_pct` (default 20%)
  - `max_exposure_pct` (default 80%)
  - `max_drawdown_pct` (default 25%)
  - `max_daily_loss_pct` (default 5%)

### 4.3 Live Broker

- [ ] Broker API key and secret injected via **environment variable or secret store** — never in code
- [ ] Broker base URL set correctly (sandbox vs production endpoint)
- [ ] Smart order router venues configured (NSE, BSE)
- [ ] Order rate limits understood and configured

> **⚠️ Live trading safety gates:**
> - [ ] Kill switch binding verified (RiskEngine kills trades on signal)
> - [ ] Emergency stop procedure documented and assigned to an operator
> - [ ] Maximum daily loss circuit breaker configured

---

## 5. Security Checklist

### 5.1 Secrets Management

- [ ] No hardcoded secrets in source code (`git grep -n "change-me\|secret\|password\|quantlab123" -- :!*.md :!*.example :!.env.example`)
- [ ] `SECRET_KEY` is a long random value (min 32 bytes)
- [ ] `detect-private-key` pre-commit hook active
- [ ] Kubernetes Secrets exist and base64-encoded:
  ```bash
  kubectl get secrets -n quantlab
  ```
- [ ] `.env` file has `600` permissions: `chmod 600 .env`
- [ ] No secrets in CI/CD logs or environment dumps

### 5.2 JWT & API Security (`services/gateway/main.py`)

- [ ] `SECRET_KEY` in JWT handler replaced (not `"dev-secret-change-in-production"`)
- [ ] `ACCESS_TOKEN_EXPIRE_HOURS` reduced for production (default: 24h)
- [ ] CORS origins restricted (not `["*"]` in production)
- [ ] Rate limiting parameters confirmed (default: 60 req/min per IP)
- [ ] API key revocation procedure documented

### 5.3 Network Security

- [ ] All internal service ports are **ClusterIP** only (no public exposure)
- [ ] Reverse proxy (nginx/ingress) handles TLS termination
- [ ] Ingress TLS enabled in Helm values (`tls: true`)
- [ ] PostgreSQL only accessible from within the cluster
- [ ] Redis protected with `requirepass` in production (currently disabled in Helm values)
- [ ] Neo4j port (7474/7687) not exposed outside cluster
- [ ] RabbitMQ management port (15672) restricted

---

## 6. Monitoring Setup

### 6.1 Prometheus

- [ ] Prometheus scraping configured for all service endpoints
- [ ] Alert rules loaded (`deploy/prometheus/alert-rules.yaml`):
  - [ ] `HighErrorRate` — error rate > 5% for 5 min (critical)
  - [ ] `ServiceDown` — any namespace service down > 1 min (critical)
  - [ ] `HighRequestLatency` — P95 > 2s for 5 min (warning)
  - [ ] `HighActiveOrders` — > 100 active orders (warning)
  - [ ] `PodRestarting` — frequent restarts (warning)
  - [ ] `MemoryPressure` — pod memory > 90% (warning)
- [ ] Alert receiver configured (PagerDuty/Slack/email)

### 6.2 Grafana

- [ ] Dashboard provisioned (`deploy/grafana/dashboard.json`)
- [ ] Prometheus datasource linked (`DS_PROMETHEUS`)
- [ ] Key panels verified after first data ingest:
  - Request rate per service
  - P99 latency
  - Active orders
  - Error rate per service
  - CPU & Memory by pod

### 6.3 HealthMonitor (application-level)

- [ ] `HealthMonitor` instances started in all services
- [ ] Broker connectivity health check wired
- [ ] Market data freshness check configured (default: 5 min staleness threshold)
- [ ] Execution latency threshold set (default: 5000ms)
- [ ] Auto-trading pause on critical health failures verified
- [ ] Manual resume procedure documented

### 6.4 Operational Dashboard

- [ ] `OperationalDashboard` rendering endpoint accessible
- [ ] Metrics visible: trade count, open positions, PnL, CPU, RAM, uptime
- [ ] Strategy health: total / active / degraded
- [ ] Experiment tracking: total / running / promoted

### 6.5 Logging

- [ ] `LOG_LEVEL=INFO` (not DEBUG)
- [ ] Log rotation configured: max 100 MB per file, 30-day retention
- [ ] Structured logging (structlog) verified — logs are JSON-parsable
- [ ] Centralized log aggregation (ELK/Loki) configured

---

## 7. Performance Baseline Verification

### 7.1 Latency Budgets

| Component | Threshold | Measured |
|---|---|---|
| Broker order placement | < 5000ms | `_ ms` |
| Market data fetch | < 2000ms | `_ ms` |
| Signal processing | < 1000ms | `_ ms` |
| Risk check evaluation | < 500ms | `_ ms` |
| API P95 response time | < 2000ms | `_ ms` |

- [ ] Latency baselines recorded for comparison after deployment

### 7.2 Resource Quotas

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Replicas |
|---|---|---|---|---|---|
| auth-gateway | 200m | 400m | 256Mi | 512Mi | 2 |
| research-engine | 250m | 500m | 256Mi | 512Mi | 2 |
| strategy-engine | 250m | 500m | 256Mi | 512Mi | 2 |
| risk-engine | 250m | 500m | 256Mi | 512Mi | 2 |
| portfolio-engine | 250m | 500m | 256Mi | 512Mi | 2 |
| execution-engine | 250m | 500m | 256Mi | 512Mi | 2 |

- [ ] HPA configured: CPU at 70%, memory at 80%, min 2 / max 10-20 replicas
- [ ] `kubectl top pods` shows no throttling after load test

### 7.3 Load Test

- [ ] 100 concurrent API requests complete with < 5% error rate
- [ ] 10 concurrent order submissions processed without queue buildup
- [ ] Backtest workload completes within expected time
- [ ] Database connection pool not exhausted under load

---

## 8. Rollback Plan

### 8.1 Application Rollback (Kubernetes)

```bash
# Helm rollback
helm rollback quantlab <revision>

# kubectl rollout undo
kubectl rollout undo deployment/auth-gateway -n quantlab
kubectl rollout undo deployment/research-engine -n quantlab
kubectl rollout undo deployment/strategy-engine -n quantlab
kubectl rollout undo deployment/risk-engine -n quantlab
kubectl rollout undo deployment/portfolio-engine -n quantlab
kubectl rollout undo deployment/execution-engine -n quantlab
```

- [ ] Previous stable Helm revision known: `helm history quantlab`
- [ ] Rollback tested in staging environment
- [ ] Rollback timeout: expect < 2 minutes

### 8.2 Database Rollback (Alembic)

```bash
# Check current revision
poetry run alembic current

# Revert one step
poetry run alembic downgrade -1

# Revert to specific revision
poetry run alembic downgrade <revision_hash>
```

- [ ] Alembic migration scripts are reversible (no destructive `downgrade`)
- [ ] Database backup taken before deployment: `pg_dump quantlab > pre-deploy.sql`

### 8.3 State Recovery (Checkpoint System)

- [ ] `Checkpointer` produces periodic snapshots of all 17 namespaces
- [ ] Latest checkpoint verified: `checkpointer.latest_checkpoint()`
- [ ] `RecoverySystem.recover()` can restore from checkpoints
- [ ] `WriteQueue` drained before shutdown to prevent data loss

### 8.4 Trigger Criteria

- [ ] Error rate > 5% sustained for 5min → **auto-rollback**
- [ ] P95 latency > 5s → **investigate, possible rollback**
- [ ] Any service down > 2min → **auto-rollback**
- [ ] Trading engine executing orders despite risk check failures → **immediate rollback**

### 8.5 Communication

- [ ] Rollback notification sent to team channel
- [ ] Root cause investigation initiated within 1 hour
- [ ] Deployment tagged with git tag for traceability

---

## 9. Post-deployment Validation

### 9.1 Service Health

- [ ] All pods `Running` and ready: `kubectl get pods -n quantlab`
- [ ] All services have `Endpoints`: `kubectl get ep -n quantlab`
- [ ] Ingress routes correctly: `curl https://quantlab.example.com/health`
- [ ] Auth gateway `/health` returns `{"status": "ok"}`

### 9.2 Data Layer

- [ ] Database migration at expected revision: `poetry run alembic current`
- [ ] PersistenceStore writable: store a test key, read it back, delete it
- [ ] Redis cache warm and responsive
- [ ] Qdrant collections exist (if knowledge graph enabled)

### 9.3 Trading Pipeline

- [ ] Broker connection established (paper or live): `HealthMonitor.status.broker_connected == True`
- [ ] Market data pipeline fetches symbols without errors
- [ ] Signal processing chain completes end-to-end
- [ ] Paper trading loop initializes without exceptions
- [ ] Kill switch disables trading when triggered
- [ ] Portfolio integrity check passes: `PortfolioEngine.verify_integrity()`

### 9.4 Observability

- [ ] Prometheus targets all `UP`: check target list in Prometheus UI
- [ ] Grafana dashboard shows non-zero metrics across all panels
- [ ] Alerts fire correctly (test with a known trigger, then resolve)
- [ ] Logs flowing to central aggregator

### 9.5 E2E Smoke Test

```bash
# 1. Fetch market data
poetry run python -c "from packages.market.data_pipeline import fetch_bars; import asyncio; print(asyncio.run(fetch_bars('RELIANCE', use_cache=False)))"

# 2. Run a backtest
poetry run python -c "
from packages.backtesting.engine import BacktestEngine
from packages.domain.models import BacktestConfig
from decimal import Decimal
cfg = BacktestConfig(initial_capital=Decimal('100000'))
print('Backtest config OK')
"

# 3. Place a paper order
poetry run python -c "
from packages.broker.gateway import PaperBroker, BrokerConfig
from packages.domain.models import Order, Side, OrderType
from decimal import Decimal
import asyncio
broker = PaperBroker(BrokerConfig(mode='paper'))
o = Order(id='smoke-1', strategy_id='s1', portfolio_id='p1', symbol='RELIANCE', side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal('2500'))
print(asyncio.run(broker.place_order(o)))
"

# 4. Health check
poetry run python -c "from packages.health.monitor import HealthMonitor; h=HealthMonitor(); print('Healthy:', h.all_healthy())"
```

- [ ] All smoke tests pass sequentially

### 9.6 Sign-off

- [ ] Pre-deployment checklist completed and signed
- [ ] Load test results within baseline
- [ ] Monitoring dashboard green for 15+ minutes after deployment
- [ ] No unexpected alerts firing
- [ ] Rollback plan documented and accessible
- [ ] Deployment tagged: `git tag deploy-$(date +%Y%m%d-%H%M)`
