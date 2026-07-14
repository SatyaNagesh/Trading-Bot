# QuantLab AI — Agent Communication Protocol

> **How Agents Talk to Each Other**  
> Version 1.0 | Last Updated: July 2026

---

## Protocol Overview

All inter-agent communication follows a structured messaging protocol built on top of the Event Bus (see `14_EVENT_BUS_SPEC.md`).

---

## Message Format

### Standard Envelope

```json
{
  "version": "1.0",
  "message_id": "msg_20260714_001",
  "trace_id": "trace_abc123",
  "sender": {
    "agent_id": "researcher-001",
    "agent_type": "Research Scientist",
    "instance_id": "researcher-001-instance-5"
  },
  "recipient": {
    "agent_id": "strategist-001",
    "agent_type": "Strategy Architect",
    "delivery": "direct"
  },
  "message_type": "command",
  "priority": "normal",
  "timestamp": "2026-07-14T10:30:00Z",
  "ttl": 3600,
  "payload": { }
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| version | Yes | Protocol version |
| message_id | Yes | Unique message identifier |
| trace_id | Yes | Trace identifier for request chains |
| sender | Yes | Agent identity information |
| recipient | Yes | Target agent and delivery mode |
| message_type | Yes | command, event, query, response |
| priority | Yes | critical, high, normal, low |
| timestamp | Yes | ISO 8601 UTC timestamp |
| ttl | No | Time-to-live in seconds |
| payload | Yes | Message content |

---

## Message Types

### 1. Command
Request another agent to perform an action.

```json
{
  "message_type": "command",
  "payload": {
    "command": "validate_strategy",
    "parameters": {
      "strategy_id": "strat_042",
      "validation_level": "full"
    },
    "deadline": "2026-07-14T12:00:00Z",
    "response_required": true
  }
}
```

### 2. Event
Notify other agents of something that happened.

```json
{
  "message_type": "event",
  "payload": {
    "event_type": "hypothesis_created",
    "event_data": {
      "hypothesis_id": "hyp_015",
      "title": "Monday morning gap reversal in NSE large caps"
    },
    "status": "success"
  }
}
```

### 3. Query
Request information from another agent.

```json
{
  "message_type": "query",
  "payload": {
    "query_type": "get_strategy_performance",
    "parameters": {
      "strategy_id": "strat_042",
      "metrics": ["sharpe", "max_dd", "win_rate"],
      "timeframe": "1m"
    }
  }
}
```

### 4. Response
Reply to a command or query.

```json
{
  "message_type": "response",
  "payload": {
    "original_message_id": "msg_20260714_001",
    "status": "success",
    "data": {
      "sharpe": 1.42,
      "max_dd": -0.15,
      "win_rate": 0.62
    },
    "confidence": 0.95,
    "warnings": []
  }
}
```

---

## Delivery Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| direct | Point-to-point to specific agent | Commands, queries |
| broadcast | To all agents | System announcements |
| topic | To agents subscribed to a topic | Events by category |
| round-robin | To next available agent | Load-balanced tasks |

---

## Priority Levels

| Level | Response SLA | Example |
|-------|-------------|---------|
| critical | < 30 seconds | Risk limit breach |
| high | < 5 minutes | Execution failure |
| normal | < 1 hour | Standard task |
| low | < 24 hours | Documentation update |

---

## Message Flow Patterns

### Request-Response (Sync)
```
Agent A ──Command──► Agent B
Agent A ◄──Response── Agent B
```

### Fire-and-Forget (Async)
```
Agent A ──Event────► Message Queue
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Agent B      Agent C      Agent D
```

### Publish-Subscribe
```
Agent A ──Event(topic)──► Event Bus
                           │
                    ┌──────┼──────┐
                    ▼      ▼      ▼
                Subscribers filtering by topic
```

### Chained Pipeline
```
Agent A ──► Agent B ──► Agent C ──► Agent D
```

---

## Error Handling

### Error Response Format
```json
{
  "message_type": "response",
  "payload": {
    "original_message_id": "msg_20260714_001",
    "status": "error",
    "error": {
      "code": "CAPABILITY_ERROR",
      "message": "Strategy validation is beyond current capacity",
      "details": {
        "current_load": 0.95,
        "estimated_available_at": "2026-07-14T11:00:00Z"
      }
    },
    "suggested_action": "Retry after 30 minutes or escalate"
  }
}
```

### Error Codes
| Code | Meaning | Action |
|------|---------|--------|
| CAPABILITY_ERROR | Agent cannot perform task | Retry/Route elsewhere |
| RESOURCE_EXHAUSTED | Agent at capacity | Wait and retry |
| VALIDATION_ERROR | Invalid request | Fix and resend |
| TIMEOUT | Operation exceeded deadline | Check status |
| CONSTITUTIONAL_VIOLATION | Task violates constitution | Escalate to human |

---

## Security

### Authentication
Every message must include a valid agent token:
```
Authorization: Bearer <agent_jwt_token>
```

### Encryption
Sensitive payload fields must be encrypted:
```json
{
  "payload": {
    "__encrypted__": true,
    "ciphertext": "base64_encrypted_data",
    "algorithm": "AES-256-GCM"
  }
}
```

---

## Protocol Compliance

All agents must:
1. Implement the standard message format
2. Include trace_id in all messages
3. Handle timeouts gracefully
4. Log all messages for audit
5. Respect priority levels
6. Include confidence in responses
7. Never expose credentials in messages
8. Acknowledge receipt within 5 seconds
