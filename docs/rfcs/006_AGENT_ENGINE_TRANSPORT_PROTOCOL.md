# RFC-006: Agent→Engine Transport Protocol

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

The 8 AI agents (doc 35 Section IV) need to call 15 engines, but no transport protocol is defined. Current docs are ambiguous:
- Doc 09 (Communication Protocol) defines inter-agent message types
- Doc 14 (Event Bus) defines async events
- Doc 16 (API Spec) defines REST endpoints

But there is no decision on: Do agents call engines via synchronous RPC or async events? When is each appropriate? What is the fallback if an engine is down?

## Proposed Protocol

### Dual Transport Model

```
┌──────────────────────────────────────────────┐
│                 AI Agent                       │
│                                                │
│  ┌────────────────┐  ┌──────────────────┐    │
│  │  gRPC Call     │  │  Event Bus       │    │
│  │  (sync, query) │  │  (async, action)  │    │
│  └────────┬───────┘  └────────┬─────────┘    │
└───────────┼────────────────────┼──────────────┘
            │                    │
     ┌──────▼──────┐     ┌──────▼──────┐
     │   Engine     │     │   Engine     │
     │   (gRPC)     │     │  (Consumer)  │
     └─────────────┘     └──────────────┘
```

### Synchronous (gRPC) — When to Use

| Scenario | Example | Timeout |
|----------|---------|---------|
| Query state | "What is current VaR?" | 5s |
| Validate input | "Is this strategy valid?" | 10s |
| Compute metric | "Compute Sharpe ratio" | 30s |
| Health check | "Is engine alive?" | 2s |

### Asynchronous (Event Bus) — When to Use

| Scenario | Example | Pattern |
|----------|---------|---------|
| Trigger backtest | "Run backtest on strategy X" | Request → callback |
| Risk alert | "Drawdown threshold breached" | Fire-and-forget |
| Data pipeline | "Fetch new market data" | Choreography |
| Long-running | "Optimize parameters" | Poll status |

### gRPC Service Definition Pattern

```protobuf
service StrategyEngine {
  rpc GetSignals(GetSignalsRequest) returns (GetSignalsResponse);
  rpc Validate(ValidateRequest) returns (ValidateResponse);
  rpc GetStatus(GetStatusRequest) returns (GetStatusResponse);
}

message GetSignalsRequest {
  string strategy_id = 1;
  MarketContext context = 2;
}

message GetSignalsResponse {
  repeated Signal signals = 1;
  float compute_time_ms = 2;
}
```

### Event Schema Pattern

```json
{
  "event_id": "evt_001",
  "type": "backtest.completed",
  "source": "BacktestEngine",
  "target": "ValidationAgent",
  "timestamp": "2026-07-14T12:00:00Z",
  "payload": {
    "strategy_id": "strat_042",
    "result_id": "bt_089",
    "sharpe_ratio": 1.52
  }
}
```

### Circuit Breaker & Retry

| Engine | Timeout | Retries | Circuit Breaker |
|--------|---------|---------|-----------------|
| DataEngine | 30s | 2 | 5 failures → 30s open |
| BacktestEngine | 300s | 1 | N/A (long-running) |
| RiskEngine | 5s | 3 | 3 failures → 10s open |
| ExecutionEngine | 10s | 0 (idempotent) | 2 failures → 5s open |

### Changes Required

| Document | Change |
|----------|--------|
| doc 09 | Add transport section: gRPC for sync, Event Bus for async |
| doc 14 | Add event schema standard for engine events |
| doc 16 | Add gRPC service definitions alongside REST |
| doc 35 | Add transport protocol to Section IV agent specs |

## Action

- [ ] Update doc 09 with dual transport model
- [ ] Add gRPC service definition examples to doc 16
