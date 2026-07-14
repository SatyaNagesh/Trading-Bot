# QuantLab AI — CI/CD Pipeline

> **Automated Quality Gates**  
> Version 1.0 | Last Updated: July 2026

---

## Pipeline Overview

```
Code Push → Lint → Test → Build → Stage → Validate → Deploy
```

---

## CI Pipeline (Every Push)

### Stage 1: Lint & Format
```yaml
name: Lint
steps:
  - ruff check .
  - ruff format --check .
  - mypy packages/ services/
```

### Stage 2: Unit Tests
```yaml
name: Unit Tests
steps:
  - pytest tests/unit/ -x --cov=packages --cov=services
  - coverage report --fail-under=90
```

### Stage 3: Integration Tests
```yaml
name: Integration Tests
services:
  postgres:
    image: postgres:17
  qdrant:
    image: qdrant/qdrant
  redis:
    image: redis:7
    
steps:
  - pytest tests/integration/ -x
```

### Stage 4: Build & Security Scan
```yaml
name: Build
steps:
  - docker build -t quantlab-ai:${{ github.sha }}
  - trivy image quantlab-ai:${{ github.sha }}
```

---

## CD Pipeline (Merge to Main)

### Stage 5: Staging Deployment
```yaml
name: Deploy to Staging
environment: staging
approval: automatic

steps:
  - docker compose -f docker/docker-compose.staging.yml up -d
  - pytest tests/e2e/ --base-url=https://staging.quantlab.ai
  - safety check
```

### Stage 6: Validation
```yaml
name: Validation
approval: manual (required)

checks:
  - All E2E tests pass
  - Performance tests within SLA
  - Security scan passes
  - No regressions detected
  - Documentation updated
```

### Stage 7: Production Deployment
```yaml
name: Deploy to Production
approval: manual (required)

strategy:
  type: rolling-update
  max_surge: 25%
  max_unavailable: 0
  
health_check:
  path: /api/v1/health
  timeout: 30s
  period: 10s
  
rollback:
  automatic: true
  trigger: health_check fails 3 times
```

---

## Pipeline Configuration

```yaml
# .github/workflows/ci.yml
name: QuantLab CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install poetry && poetry install
      - run: poetry run ruff check .
      - run: poetry run mypy packages/ services/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - run: pip install poetry && poetry install
      - run: poetry run pytest tests/unit/ tests/integration/ -x --cov=packages
      - run: poetry run coverage report --fail-under=85

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install safety
      - run: safety check
      - run: pip install bandit
      - run: bandit -r packages/ -ll

  e2e:
    runs-on: ubuntu-latest
    needs: [lint, test, security]
    steps:
      - run: docker compose -f docker/docker-compose.staging.yml up -d
      - run: pytest tests/e2e/ --base-url=http://localhost:8000
```

---

## Branch Strategy

```
main ──────── Production (protected)
  │
  └── develop ──── Staging (default branch for PRs)
       │
       ├── feature/* ──── New features
       ├── fix/* ──────── Bug fixes
       ├── research/* ─── Research experiments
       └── docs/* ─────── Documentation
```

---

## Quality Gates

### Gate 1: Pre-Commit (Local)
- `make lint` passes
- `make test` passes
- No TODO without issue reference

### Gate 2: CI (Push)
- All lint checks pass
- All unit/integration tests pass
- Coverage meets minimum
- Security scan passes

### Gate 3: PR Review
- Two approvals for production changes
- One approval for other changes
- All CI checks green

### Gate 4: Pre-Deploy
- All E2E tests pass
- Performance benchmarks within range
- No known critical issues
- Documentation updated

---

## Artifact Management

```yaml
artifacts:
  docker_image:
    registry: ghcr.io
    tag: ${{ github.sha }}
    retention: 30 days
  
  test_reports:
    path: reports/
    retention: 90 days
    
  coverage_reports:
    path: coverage/
    retention: 90 days
```

---

## Rollback Procedure

```yaml
rollback:
  trigger:
    - Health check fails 3 consecutive times
    - Error rate increases > 5%
    - P95 latency increases > 50%
    - Manual trigger from operator
  
  procedure:
    1. Revert to previous Docker image tag
    2. Run database rollback migration if needed
    3. Verify health check passes
    4. Notify team via Slack/Email
  
  duration:
    automatic: < 5 minutes
    manual: < 15 minutes
```
