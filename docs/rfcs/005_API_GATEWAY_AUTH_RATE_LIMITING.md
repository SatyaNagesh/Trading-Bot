# RFC-005: API Gateway, Authentication & Rate Limiting

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

Doc 16 (API Specification) defines REST endpoints but lacks:
- API Gateway layer for routing, rate limiting, and load balancing
- Authentication flow (JWT, OAuth2, agent tokens)
- Authorization model (RBAC implementation)
- Rate limiting strategy
- API versioning scheme

Doc 26 (Security Architecture) defines security layers at high level but doesn't specify implementation.

## Proposed Solution

### Architecture

```
Client → API Gateway (Kong/Traefik) → Auth Service → Rate Limiter → Service
         │
         ├── JWT Validation
         ├── Rate Limit Check
         ├── RBAC Enforcement
         └── Request Logging
```

### Authentication Flows

| Actor | Method | Token Type | Expiry |
|-------|--------|------------|--------|
| Human (dashboard) | OAuth2 + Google/GitHub | JWT | 24h |
| Human (CLI) | API Key | JWT | 90d |
| AI Agent | Agent Identity Token | mTLS + JWT | 1h |
| Service | mTLS | Certificate | 1y |

### Role-Based Access Control

| Role | Permissions |
|------|------------|
| `admin` | Full access, limit changes, user management |
| `researcher` | Read/write hypotheses, strategies, backtests |
| `trader` | Execute trades, read portfolio |
| `viewer` | Read-only dashboard |
| `agent` | Engine-specific scoped access |

### Rate Limiting

| Tier | Requests/Min | Burst | Scope |
|------|-------------|-------|-------|
| Human UI | 60 | 10 | Per user |
| CLI | 120 | 20 | Per API key |
| Agent | 300 | 50 | Per agent |
| Backtest | 10 | 2 | Per service (async) |

### API Versioning

```yaml
versioning:
  scheme: "URL path prefix"
  format: "/api/v1/..."
  current: "v1"
  deprecation: "6 months notice"
  sunset: "12 months notice"
```

### Gateway Responsibilities

```
1. TLS termination
2. JWT validation / mTLS handshake
3. Rate limit enforcement (sliding window)
4. RBAC check against policy engine
5. Request routing to appropriate service
6. Request/response logging to Loki
7. Circuit breaker per upstream service
```

### Changes Required

| Document | Change |
|----------|--------|
| doc 16 | Add gateway section, auth flow, rate limiting, versioning |
| doc 26 | Add RBAC implementation details, token flows |

## Action

- [ ] Update doc 16 with gateway/auth/rate-limiting sections
- [ ] Update doc 26 with auth implementation details
