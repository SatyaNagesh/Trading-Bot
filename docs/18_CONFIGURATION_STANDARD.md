# QuantLab AI — Configuration Standard

> **How We Configure the System**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

QuantLab AI uses a layered configuration system with clear precedence, secret management, and environment-specific overrides.

---

## Configuration Hierarchy

```
1. Command-line arguments (highest priority)
2. Environment variables
3. Local config file (config.local.yaml)
4. Environment config file (config.prod.yaml)
5. Default config file (config.default.yaml)
6. Hard-coded defaults (lowest priority)
```

---

## Configuration Files

### Directory Structure
```
config/
├── default.yaml          # Default configuration
├── development.yaml      # Development overrides
├── staging.yaml          # Staging overrides
├── production.yaml       # Production overrides
├── local.yaml            # Local overrides (gitignored)
├── secrets.yaml          # Encrypted secrets (gitignored)
└── schema.yaml           # Configuration schema
```

### Default Configuration
```yaml
# config/default.yaml
system:
  name: "QuantLab AI"
  environment: "development"
  log_level: "INFO"
  debug: false

api:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  rate_limit: 1000
  cors_origins: ["http://localhost:3000"]

database:
  postgresql:
    host: "localhost"
    port: 5432
    database: "quantlab"
    pool_size: 10
    max_overflow: 20
  
  qdrant:
    host: "localhost"
    port: 6333
  
  redis:
    host: "localhost"
    port: 6379
    db: 0

broker:
  default: "zerodha"
  paper_trading: true
  max_retries: 3

risk:
  max_position_size: 0.1
  max_portfolio_risk: 0.02
  max_drawdown: 0.2
  var_confidence: 0.95

research:
  min_data_years: 3
  min_trades_for_validation: 1000
  significance_level: 0.05
  walk_forward_windows: 10

monitoring:
  metrics_enabled: true
  tracing_enabled: true
  health_check_interval: 30
```

---

## Environment Variables

### Naming Convention
```
QUANTLAB_<SECTION>_<KEY>
```

### Examples
```bash
QUANTLAB_API_PORT=8000
QUANTLAB_DATABASE_POSTGRESQL_HOST=localhost
QUANTLAB_DATABASE_POSTGRESQL_PASSWORD=secret
QUANTLAB_BROKER_ZERODHA_API_KEY=your_api_key
QUANTLAB_MONITORING_METRICS_ENABLED=true
```

### Required Environment Variables
```bash
QUANTLAB_SECRET_KEY           # Application secret key
QUANTLAB_DATABASE_POSTGRESQL_PASSWORD  # Database password
QUANTLAB_DATABASE_POSTGRESQL_HOST      # Database host
```

---

## Secrets Management

### Local Development
```yaml
# .env file (gitignored)
QUANTLAB_SECRET_KEY=dev-secret-key
QUANTLAB_DATABASE_POSTGRESQL_PASSWORD=dev-password
```

### Production
```yaml
# HashiCorp Vault (preferred)
# AWS Secrets Manager
# Azure Key Vault
# Google Secret Manager
```

### Encrypted Config File
```yaml
# config/secrets.yaml.enc (encrypted)
# Decrypted at runtime with master key
api_keys:
  zerodha: "enc:AES256:..."
  polygon: "enc:AES256:..."
```

---

## Configuration Schema

```yaml
# config/schema.yaml
system:
  environment:
    type: string
    enum: [development, staging, production]
    required: true

database:
  postgresql:
    host:
      type: string
      required: true
    port:
      type: integer
      default: 5432
    pool_size:
      type: integer
      default: 10
      min: 1
      max: 100
```

---

## Feature Flags

Feature flags enable progressive rollout:

```yaml
features:
  ml_engine:
    enabled: false
    rollout_percentage: 0
    description: "Machine Learning Engine"
  
  new_backtest_engine:
    enabled: true
    rollout_percentage: 50
    description: "New backtesting engine V2"
  
  ai_agents:
    enabled: true
    rollout_percentage: 100
    description: "AI agent system"
```

---

## Configuration Validation

On startup, the system validates:
1. All required keys are present
2. Types match schema definitions
3. Values are within allowed ranges
4. No conflicting configurations
5. Secrets can be decrypted
6. Connections can be established

---

## Runtime Configuration

Some settings can be modified at runtime:

```yaml
runtime_configurable:
  - log_level
  - risk.max_position_size
  - risk.max_portfolio_risk
  - features.*.enabled
  - monitoring.metrics_enabled
```

Runtime changes are:
- Logged for audit
- Non-persistent (reset on restart)
- Propagated to affected components
- Revertible
