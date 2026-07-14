# RFC-007: Error Handling & Resilience Strategy

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

No document defines:
- Error classification (recoverable vs non-recoverable)
- Retry policies per engine
- Circuit breaker thresholds
- Graceful degradation strategies
- What happens when a service is down
- Error response format across all APIs

## Proposed Solution

### Error Classification

```
Level 0: Transient
  - Network timeout, rate limited, service unavailable
  - Action: Retry with backoff (3 attempts, exponential backoff)
  - Log level: WARN

Level 1: Recoverable
  - Invalid input, missing data, stale cache
  - Action: Return error to caller, log, no retry
  - Log level: ERROR

Level 2: Critical
  - Database corruption, broker disconnect, position mismatch
  - Action: Alert human, pause all trading, generate incident report
  - Log level: CRITICAL

Level 3: Catastrophic
  - System-wide failure, security breach, constitutional violation
  - Action: Emergency shutdown, immutable evidence log, human pager
  - Log level: FATAL
```

### Error Response Format

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Retry after 30s.",
    "details": {
      "retry_after_seconds": 30,
      "limit": 100,
      "window_seconds": 60
    },
    "request_id": "req_abc123",
    "timestamp": "2026-07-14T12:00:00Z"
  }
}
```

### Standard Error Codes

| Code | HTTP Status | Level | Description |
|------|-------------|-------|-------------|
| `INVALID_INPUT` | 400 | L1 | Malformed request |
| `UNAUTHORIZED` | 401 | L1 | Missing/invalid auth |
| `FORBIDDEN` | 403 | L1 | Insufficient permissions |
| `NOT_FOUND` | 404 | L1 | Resource not found |
| `RATE_LIMITED` | 429 | L0 | Rate limit exceeded |
| `SERVICE_UNAVAILABLE` | 503 | L0 | Engine temporarily down |
| `DEPENDENCY_FAILURE` | 502 | L1 | Downstream service failed |
| `INTERNAL_ERROR` | 500 | L2 | Unexpected engine error |
| `DATA_INTEGRITY` | 500 | L2 | Database/data corruption |
| `BROKER_DISCONNECT` | 502 | L2 | Broker connection lost |
| `CONSTITUTIONAL_VIOLATION` | 403 | L3 | Action violates 12 Laws |

### Retry Policies

| Engine | Max Retries | Backoff | Jitter |
|--------|-------------|---------|--------|
| Data Pipeline | 3 | Exponential (1s, 4s, 16s) | ±500ms |
| Backtest | 2 | Linear (30s, 60s) | No |
| Risk Engine | 3 | Exponential (100ms, 400ms, 1.6s) | ±100ms |
| Execution | 0 (fail fast) | N/A | N/A |
| Broker Gateway | 2 | Exponential (500ms, 2s) | ±200ms |

### Graceful Degradation

| Failed Engine | Degraded Behavior |
|---------------|-------------------|
| Data Engine | Use cached data last 24h, pause new research |
| Risk Engine | Use last known risk snapshot, reduce all sizes by 50% |
| Backtest Engine | Queue backtest requests, serve cached results |
| Execution Engine | Pause all trading, alert human |
| Knowledge Graph | Disable graph queries, serve DB fallback |
| ML Engine | Use heuristic fallback, log degradation |

### Changes Required

| Document | Change |
|----------|--------|
| New appendix to doc 21 | Error handling standards for all code |
| doc 14 | Add error event types to event bus |
| doc 16 | Add error response format to API spec |
| doc 26 | Add incident response to security architecture |

## Action

- [ ] Create error handling standard addendum to doc 21
- [ ] Update doc 14, 16, 26 with resilience patterns
