# QuantLab AI — Event Bus Specification

> **The Nervous System**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Event Bus is the central nervous system of QuantLab AI — enabling asynchronous, decoupled communication between all services, agents, and components.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Event Bus                           │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │            Message Router (RabbitMQ)              │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐           │ │
│  │  │Exchange │ │Exchange │ │Exchange │           │ │
│  │  │  Topic  │ │  Direct │ │  Fanout │           │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘           │ │
│  │       │           │           │                  │ │
│  │  ┌────▼────┐ ┌────▼────┐ ┌────▼────┐           │ │
│  │  │ Queue 1 │ │ Queue 2 │ │ Queue 3 │           │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘           │ │
│  └───────┼───────────┼───────────┼──────────────────┘ │
│          │           │           │                     │
│     ┌────▼───┐ ┌────▼───┐ ┌────▼───┐                 │
│     │Consumer│ │Consumer│ │Consumer│                 │
│     │Agent A │ │Agent B │ │Agent C │                 │
│     └────────┘ └────────┘ └────────┘                 │
└─────────────────────────────────────────────────────┘
```

---

## Event Types

### System Events
| Event | Description | Publisher | Priority |
|-------|-------------|-----------|----------|
| system.startup | System started | Core | normal |
| system.shutdown | System shutting down | Core | normal |
| system.health_check | Health check request | Monitor | low |
| system.config_change | Configuration updated | Config | high |

### Research Events
| Event | Description | Publisher | Priority |
|-------|-------------|-----------|----------|
| research.hypothesis_created | New hypothesis | Research Scientist | normal |
| research.hypothesis_updated | Hypothesis modified | Research Scientist | normal |
| research.experiment_started | Experiment begins | Research Scientist | low |
| research.experiment_completed | Experiment ends | Research Scientist | normal |
| research.finding_discovered | Finding documented | Research Scientist | high |

### Strategy Events
| Event | Description | Publisher | Priority |
|-------|-------------|-----------|----------|
| strategy.created | New strategy defined | Strategy Architect | normal |
| strategy.updated | Strategy modified | Strategy Architect | normal |
| strategy.parameter_changed | Parameter tuned | Optimizer | low |
| strategy.ready_for_backtest | Ready to test | Strategy Architect | high |

### Backtest Events
| Event | Description | Publisher | Priority |
|-------|-------------|-----------|----------|
| backtest.started | Backtest begins | Backtest Engine | low |
| backtest.progress | Progress update | Backtest Engine | low |
| backtest.completed | Backtest done | Backtest Engine | high |
| backtest.failed | Backtest error | Backtest Engine | high |

### Execution Events
| Event | Description | Publisher | Priority |
|-------|-------------|-----------|----------|
| execution.signal_generated | Trade signal | Strategy Engine | high |
| execution.order_created | Order created | Execution Agent | critical |
| execution.order_filled | Order filled | Broker Gateway | critical |
| execution.order_failed | Order failed | Broker Gateway | critical |
| execution.position_changed | Position updated | Broker Gateway | high |

### Risk Events
| Event | Description | Publisher | Priority |
|-------|-------------|-----------|----------|
| risk.limit_approaching | Nearing limit | Risk Manager | critical |
| risk.limit_breached | Limit exceeded | Risk Manager | critical |
| risk.var_updated | VaR recalculated | Risk Manager | normal |
| risk.stress_test_complete | Stress test done | Risk Manager | normal |

---

## Exchange Types

### Topic Exchange
Routing by pattern matching on routing key:
```
research.hypothesis.*     → Matches all hypothesis events
*.completed              → Matches all completion events
execution.#              → Matches all execution events
```

### Direct Exchange
Routing by exact match:
```
risk.critical             → Only critical risk events
system.startup            → Only startup event
```

### Fanout Exchange
Broadcast to all bound queues:
```
system.announcement       → All agents
system.alert              → All monitors
```

---

## Message Structure

### Event Format
```json
{
  "event_id": "evt_20260714_001",
  "event_type": "research.hypothesis_created",
  "version": "1.0",
  "timestamp": "2026-07-14T10:30:00Z",
  "source": {
    "service": "research-engine",
    "agent": "researcher-001",
    "instance": "researcher-001-instance-5"
  },
  "correlation_id": "corr_abc123",
  "causation_id": "cause_def456",
  "priority": "normal",
  "headers": {
    "content_type": "application/json",
    "encoding": "utf-8",
    "schema_version": "2.1"
  },
  "payload": {
    "hypothesis_id": "hyp_015",
    "title": "Monday morning gap reversal",
    "status": "active"
  },
  "metadata": {
    "retry_count": 0,
    "delivery_mode": "persistent",
    "ttl": 86400
  }
}
```

---

## Delivery Guarantees

| Priority | Delivery | ACK | Retry |
|----------|----------|-----|-------|
| critical | At-least-once | Required | 5 times, immediate |
| high | At-least-once | Required | 3 times, 30s delay |
| normal | At-least-once | Optional | 2 times, 5min delay |
| low | Best-effort | None | None |

---

## Dead Letter Queue

Events that cannot be processed after retries go to DLQ:

```yaml
dead_letter_queue:
  exchange: dlq.exchange
  routing_key: dlq.#
  
  policies:
    max_retries: 5
    max_age: 7d  # Events older than 7 days are purged
    
  handlers:
    - action: log_and_notify
      conditions:
        - priority == "critical"
        - priority == "high"
    - action: alert_human
      conditions:
        - retry_count == max_retries
        - priority == "critical"
    - action: discard
      conditions:
        - age > max_age
```

---

## Event Sourcing

Critical events are stored for event sourcing:
```yaml
event_store:
  storage: PostgreSQL
  retention: permanent
  indexes:
    - event_type
    - source.agent
    - correlation_id
    - timestamp
    
  usage:
    - Audit trail
    - State reconstruction
    - Debugging
    - Performance analysis
    - Compliance reporting
```

---

## Performance Targets

| Metric | Target | Degradation Alert |
|--------|--------|-------------------|
| Throughput | > 10,000 events/sec | < 1,000 |
| Latency (p95) | < 5ms | > 50ms |
| Delivery guarantee | 99.999% | < 99.9% |
| Queue depth | < 1,000 | > 10,000 |
| Consumer lag | < 100ms | > 5s |
