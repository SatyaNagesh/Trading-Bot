# QuantLab AI — Security Architecture

> **Keeping the System Safe**  
> Version 1.1 | Last Updated: July 2026

---

## Security Principles

1. **Zero Trust** — No implicit trust, verify everything
2. **Least Privilege** — Minimum access required
3. **Defense in Depth** — Multiple security layers
4. **Secure by Default** — Security is not optional
5. **Audit Everything** — Every action is logged

---

## Authentication

### API Authentication
```yaml
method: API Key + JWT
header: Authorization: Bearer <token>
token_lifetime: 24h (access), 30d (refresh)

rate_limiting:
  per_user: 1000 req/min
  per_ip: 100 req/min
  burst: 200
```

### Agent Authentication
```yaml
method: Agent Identity Token
rotation: Every 24h
storage: Vault / environment

agent_token:
  claims:
    - agent_id
    - agent_role
    - capabilities
    - issued_at
    - expires_at
```

### Human Authentication
```yaml
method: OAuth 2.0 / SSO
providers:
  - GitHub
  - Google
  - Email + Password (with 2FA)

password_policy:
  min_length: 12
  require_special: true
  require_numbers: true
  require_uppercase: true
  hash: bcrypt
```

---

## Authorization

### Role-Based Access Control
```yaml
roles:
  admin:
    - full_system_access
    - user_management
    - configuration
  
  researcher:
    - read_market_data
    - create_hypotheses
    - run_backtests
    - view_portfolios
  
  trader:
    - execute_trades
    - manage_positions
    - view_risk_metrics
  
  viewer:
    - read_public_data
    - view_reports
  
  agent:
    - assigned_tasks_only
    - read_required_data
    - write_task_results
```

### API Permissions
```yaml
permissions:
  market_data:read: { roles: [admin, researcher, trader, viewer] }
  market_data:write: { roles: [admin] }
  trade:execute: { roles: [admin, trader] }
  trade:cancel: { roles: [admin, trader] }
  hypothesis:create: { roles: [admin, researcher] }
  strategy:deploy: { roles: [admin] }
  config:modify: { roles: [admin] }
  user:manage: { roles: [admin] }
```

---

## Credential Management

### Never Commit Credentials
```yaml
# .gitignore
.env
config/local.yaml
config/secrets.yaml
*.key
*.pem
credentials.json
service-account.json
```

### Environment Variables
```bash
# Never in code, always in environment
QUANTLAB_SECRET_KEY=${SECRET_KEY}
QUANTLAB_DATABASE_POSTGRESQL_PASSWORD=${DB_PASSWORD}
QUANTLAB_BROKER_API_KEY=${BROKER_KEY}
```

### Secret Storage
```yaml
development:
  method: .env file (gitignored)

production:
  method: HashiCorp Vault / AWS Secrets Manager
  rotation: 90 days
  audit: Every access logged
```

---

## Network Security

### Service Mesh
```yaml
internal_communication:
  encryption: mTLS
  authentication: Mutual TLS Certificates
  authorization: Service Identity

external_communication:
  encryption: TLS 1.3
  certificates: Let's Encrypt / Internal CA
```

### Firewall Rules
```yaml
ingress:
  - port: 443 (HTTPS)
    source: 0.0.0.0/0
  - port: 80 (HTTP - redirect to HTTPS)
    source: 0.0.0.0/0

internal:
  - postgres: 5432
    source: app_network
  - qdrant: 6333
    source: app_network
  - redis: 6379
    source: app_network
  - rabbitmq: 5672
    source: app_network

egress:
  - allow: broker_api_ips
  - allow: data_source_ips
  - block: all_other
```

---

## AI Security

### Prompt Injection Protection
```yaml
ai_security:
  input_sanitization:
    - Remove control characters
    - Validate format
    - Check for injection patterns
  
  output_verification:
    - Validate against schema
    - Check for sensitive data leakage
    - Verify constraints
  
  rate_limiting:
    max_requests_per_minute: 60
    max_tokens_per_request: 4000
  
  content_filter:
    - Block trading instructions outside parameters
    - Block access to system configuration
    - Block credential requests
```

### Agent Isolation
```yaml
agent_isolation:
  execution: Sandboxed environment
  data_access: Need-to-know basis
  communication: Encrypted and authenticated
  resources: CPU/memory limits
  actions: Logged and auditable
```

---

## Data Security

### At Rest
```yaml
encryption:
  method: AES-256-GCM
  key_management: AWS KMS / Vault
  scope: All sensitive data in PostgreSQL
  
  specific:
    - API keys: Encrypted
    - Credentials: Encrypted
    - PII: Encrypted
    - Trade data: Encrypted at column level
```

### In Transit
```yaml
encryption:
  method: TLS 1.3
  internal: mTLS
  external: TLS 1.3 minimum
  certificates: Auto-renewed via cert-manager
```

---

## Audit Logging

```yaml
audit_events:
  authentication:
    - login_success
    - login_failure
    - token_refresh
    - token_revocation
  
  authorization:
    - permission_denied
    - role_change
    - access_granted
  
  data_access:
    - data_export
    - bulk_read
    - schema_change
  
  trading:
    - order_placed
    - order_cancelled
    - position_change
    - risk_limit_breach
  
  admin:
    - config_change
    - user_management
    - system_restart

audit_storage:
  retention: 7 years (compliance)
  immutable: true
  backup: Geo-redundant
```

---

---

## Section: Authentication Implementation

### Auth System Architecture

```
Auth Service (standalone service)
├── OAuth2 Provider (Google/GitHub for humans)
├── JWT Issuer (for humans, agents, services)
├── API Key Manager (for CLI users)
├── Certificate Authority (for mTLS)
├── RBAC Policy Engine
└── Session Manager (Redis-backed)
```

### JWT Token Structure

```json
{
  "sub": "user_abc123 | agent_ceo_001 | svc_data_engine",
  "role": "researcher | admin | agent | trader | viewer",
  "type": "human | agent | service",
  "scopes": ["strategies:read", "backtests:write"],
  "iat": 1700000000,
  "exp": 1700086400,
  "jti": "tid_unique_001"
}
```

### Token Validation Flow

```
1. Client presents JWT in Authorization header
2. Auth Service validates signature (RS256)
3. Checks expiry (iat, exp)
4. Checks revocation status (Redis blacklist)
5. Extracts role and scopes
6. RBAC engine checks permission for requested resource
7. Request forwarded to target service (with JWT claims in header)
```

### Agent Identity Tokens

```yaml
agent_auth:
  method: "Agent Identity Token (mTLS + short-lived JWT)"
  
  issuance:
    - "Agent spawned with unique identity"
    - "mTLS cert issued by internal CA"
    - "JWT issued with 1-hour expiry"
    - "Scoped to agent's assigned engines only"
  
  renewal:
    - "Auto-renewed by Agent Framework"
    - "Renewal requires valid mTLS"
    - "On renewal failure: agent paused"
  
  revocation:
    - "Agent terminated → token revoked"
    - "Suspicious activity → immediate revocation"
    - "Stale > 10 min → auto-revoked"
```

### RBAC Implementation

```python
# Decision matrix: role × resource → action
PERMISSIONS = {
    "admin":    {"strategies": "crud", "backtests": "crud", "trades": "crud", "users": "crud"},
    "researcher": {"strategies": "crud", "backtests": "crud", "trades": "r",    "users": ""},
    "trader":   {"strategies": "r",    "backtests": "r",    "trades": "crud", "users": ""},
    "viewer":   {"strategies": "r",    "backtests": "r",    "trades": "r",    "users": ""},
    "agent":    {"strategies": "cr",   "backtests": "cr",   "trades": "r",    "users": ""},
}
```

---

## Incident Response

```yaml
incident_response:
  tiers:
    tier_1:
      severity: low
      response: within 24h
      examples: [failed_login_attempts, minor_config_change]
      
    tier_2:
      severity: medium
      response: within 4h
      examples: [suspicious_activity, rate_limit_breach]
      
    tier_3:
      severity: high
      response: within 1h
      examples: [credential_leak, unauthorized_access]
      
    tier_4:
      severity: critical
      response: immediate
      examples: [data_breach, system_compromise]
  
  procedure:
    - Identify and isolate
    - Contain the breach
    - Eradicate the threat
    - Recover the system
    - Post-mortem analysis
    - Update security measures
```
