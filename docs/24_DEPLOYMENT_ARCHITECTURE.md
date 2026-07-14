# QuantLab AI — Deployment Architecture

> **Where the System Lives**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

QuantLab AI follows a progressive deployment strategy — starting with simple Docker Compose for development and evolving to Kubernetes for production.

---

## Deployment Tiers

### Tier 0: Local Development
```
Single machine, Docker Compose
```

**Components:**
```
quantlab-api        (FastAPI)
quantlab-worker     (Background tasks)
postgres            (Database)
qdrant              (Vector store)
redis               (Cache + pub-sub)
neo4j               (Knowledge graph)
minio               (Object storage)
rabbitmq            (Message broker)
```

### Tier 1: Staging
```
Single server, Docker Compose with production-like settings
```

**Additions:**
- Read replica for PostgreSQL
- Persistent volumes
- Backup cron jobs
- Monitoring stack (Prometheus + Grafana)
- SSL termination

### Tier 2: Production (V1)
```
Multi-server, Docker Swarm or lightweight orchestration
```

**Changes:**
- API server behind load balancer (2+ replicas)
- Worker pool (2+ workers)
- PostgreSQL primary + read replicas
- Qdrant cluster
- Redis cluster
- RabbitMQ cluster
- CDN for static assets

### Tier 3: Scale (V2+)
```
Kubernetes cluster, cloud-native
```

**Additions:**
- Auto-scaling
- Service mesh
- Multi-region
- Disaster recovery
- Blue-green deployments
- Canary releases

---

## Docker Compose (Development)

```yaml
# docker/docker-compose.yml
version: "3.8"

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - QUANTLAB_ENVIRONMENT=development
      - QUANTLAB_DATABASE_POSTGRESQL_HOST=postgres
    depends_on:
      - postgres
      - qdrant
      - redis
    volumes:
      - ../:/app
    command: uvicorn apps.api.main:app --reload --host 0.0.0.0

  worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: python -m apps.worker
    depends_on:
      - postgres
      - redis
      - rabbitmq

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: quantlab
      POSTGRES_PASSWORD: development
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/development
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

  monitor:
    image: grafana/otel-lgtm:latest
    ports:
      - "3000:3000"   # Grafana
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP

volumes:
  pgdata:
  qdrant_data:
  neo4j_data:
  minio_data:
```

---

## Dockerfile

```dockerfile
# docker/Dockerfile
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.0 \
    POETRY_HOME=/opt/poetry

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="$POETRY_HOME/bin:$PATH"
WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --only main

COPY . .

FROM base AS development
RUN poetry install --no-interaction --no-ansi
CMD ["uvicorn", "apps.api.main:app", "--reload", "--host", "0.0.0.0"]

FROM base AS production
RUN poetry install --no-interaction --no-ansi --only main
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--workers", "4"]
```

---

## Production Architecture (V1)

```
                         ┌─────────┐
                         │  CDN    │
                         └────┬────┘
                              │
                     ┌────────▼────────┐
                     │  Load Balancer   │
                     │  (nginx/traefik) │
                     └────────┬────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
     ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
     │  API    │        │  API    │        │  API    │
     │  Node 1 │        │  Node 2 │        │  Node N │
     └────┬────┘        └────┬────┘        └────┬────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Message Queue     │
                    │   (RabbitMQ)        │
                    └─────────┬──────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
     ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
     │ Worker  │        │ Worker  │        │ Worker  │
     │   1     │        │   2     │        │   N     │
     └─────────┘        └─────────┘        └─────────┘
```

---

## Kubernetes (Future)

```yaml
# kubernetes/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quantlab-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: quantlab-api
  template:
    metadata:
      labels:
        app: quantlab-api
    spec:
      containers:
      - name: api
        image: ghcr.io/quantlab-ai/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: QUANTLAB_ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
        readinessProbe:
          httpGet:
            path: /api/v1/ready
            port: 8000
```

---

## Monitoring Stack

```yaml
monitoring:
  metrics: Prometheus + Grafana
  logging: Loki + Promtail
  tracing: Tempo + OpenTelemetry
  alerting: Alertmanager + Slack/PagerDuty
  
  dashboards:
    - System Overview
    - API Performance
    - Worker Status
    - Database Health
    - Strategy Performance
    - Risk Metrics
    - AI Agent Performance
```

---

## Backup Strategy

| Data | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| PostgreSQL | Hourly | 30 days | pg_dump to S3 |
| Qdrant | Daily | 7 days | Snapshot |
| Neo4j | Daily | 7 days | Dump |
| Config | Per change | 90 days | Git |
| Models | Per training | Permanent | S3 |
