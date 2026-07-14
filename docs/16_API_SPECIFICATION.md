# QuantLab AI — API Specification

> **How to Talk to QuantLab AI**  
> Version 1.1 | Last Updated: July 2026

---

## Overview

QuantLab AI exposes multiple API surfaces for different use cases:
- **REST API** — Standard CRUD operations
- **GraphQL API** — Complex queries and data exploration
- **gRPC API** — Internal service-to-service communication
- **WebSocket API** — Real-time data streams
- **MCP API** — AI agent tool interface

---

## API Design Principles

- Resource-oriented design
- Consistent naming conventions
- Versioned from day one
- Comprehensive error responses
- Pagination for all list endpoints
- Rate limiting per client
- Authentication required for all endpoints
- Idempotency for mutating operations

---

## REST API

### Base URLs
```
Development:  http://localhost:8000/api/v1
Staging:      https://staging-api.quantlab.ai/api/v1
Production:   https://api.quantlab.ai/api/v1
```

### Standard Response Format

#### Success
```json
{
  "status": "success",
  "data": { },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-07-14T10:30:00Z",
    "version": "1.0"
  }
}
```

#### Error
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid parameter: timeframe",
    "details": {
      "field": "timeframe",
      "constraint": "must be one of: 1m, 5m, 15m, 1h, 4h, 1d"
    }
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-07-14T10:30:00Z"
  }
}
```

### Market Data Endpoints

```yaml
GET /api/v1/markets
  description: List available markets
  params:
    exchange: str (optional)
    asset_class: str (optional)
    search: str (optional)
    page: int (default: 1)
    per_page: int (default: 50)
  response: Market[]

GET /api/v1/markets/{symbol}
  description: Get market details
  response: Market

GET /api/v1/markets/{symbol}/data
  description: Get market data
  params:
    interval: str (required) [1m, 5m, 15m, 1h, 4h, 1d]
    from: datetime (required)
    to: datetime (required)
    adjust: bool (default: true)
  response: MarketData[]
```

### Research Endpoints

```yaml
POST /api/v1/hypotheses
  description: Create new hypothesis
  body: HypothesisCreate
  response: Hypothesis

GET /api/v1/hypotheses/{id}
  description: Get hypothesis details
  response: Hypothesis

GET /api/v1/hypotheses
  description: List hypotheses
  params:
    status: str (optional)
    category: str (optional)
    page: int (default: 1)
    per_page: int (default: 20)
  response: Hypothesis[]

POST /api/v1/hypotheses/{id}/test
  description: Start hypothesis testing
  body: TestConfig
  response: TestRun
```

### Strategy Endpoints

```yaml
POST /api/v1/strategies
  description: Create new strategy
  body: StrategyCreate
  response: Strategy

GET /api/v1/strategies/{id}
  description: Get strategy details
  response: Strategy

PUT /api/v1/strategies/{id}
  description: Update strategy
  body: StrategyUpdate
  response: Strategy

POST /api/v1/strategies/{id}/backtest
  description: Run backtest
  body: BacktestConfig
  response: BacktestRun

GET /api/v1/strategies/{id}/backtest/{run_id}
  description: Get backtest results
  response: BacktestResult
```

### Portfolio Endpoints

```yaml
POST /api/v1/portfolios
  description: Create portfolio
  body: PortfolioCreate
  response: Portfolio

GET /api/v1/portfolios/{id}
  description: Get portfolio details
  response: Portfolio

POST /api/v1/portfolios/{id}/rebalance
  description: Trigger rebalance
  body: RebalanceConfig
  response: RebalanceResult
```

### Agent Endpoints

```yaml
GET /api/v1/agents
  description: List agents
  response: Agent[]

GET /api/v1/agents/{id}
  description: Get agent status
  response: Agent

POST /api/v1/agents/{id}/tasks
  description: Assign task to agent
  body: TaskCreate
  response: Task
```

---

## GraphQL API

### Schema
```graphql
type Query {
  markets(exchange: String, assetClass: String): [Market!]!
  market(symbol: String!): Market
  marketData(symbol: String!, interval: String!, from: DateTime!, to: DateTime!): [MarketData!]!
  
  hypotheses(status: String, category: String): [Hypothesis!]!
  hypothesis(id: UUID!): Hypothesis
  
  strategies(status: String, type: String): [Strategy!]!
  strategy(id: UUID!): Strategy
  backtestResults(strategyId: UUID!): [BacktestResult!]!
  
  portfolios: [Portfolio!]!
  portfolio(id: UUID!): Portfolio
  
  agents: [Agent!]!
  agent(id: String!): Agent
}

type Mutation {
  createHypothesis(input: HypothesisCreate!): Hypothesis!
  updateHypothesis(id: UUID!, input: HypothesisUpdate!): Hypothesis!
  testHypothesis(id: UUID!, config: TestConfig!): TestRun!
  
  createStrategy(input: StrategyCreate!): Strategy!
  updateStrategy(id: UUID!, input: StrategyUpdate!): Strategy!
  runBacktest(strategyId: UUID!, config: BacktestConfig!): BacktestRun!
  
  createPortfolio(input: PortfolioCreate!): Portfolio!
  rebalancePortfolio(id: UUID!, config: RebalanceConfig!): RebalanceResult!
  
  assignTask(agentId: String!, task: TaskCreate!): Task!
}
```

---

## gRPC Services

### Internal Service Proto
```protobuf
service ResearchService {
  rpc CreateHypothesis (CreateHypothesisRequest) returns (Hypothesis);
  rpc GetHypothesis (GetHypothesisRequest) returns (Hypothesis);
  rpc ListHypotheses (ListHypothesesRequest) returns (ListHypothesesResponse);
  rpc TestHypothesis (TestHypothesisRequest) returns (TestRun);
}

service StrategyService {
  rpc CreateStrategy (CreateStrategyRequest) returns (Strategy);
  rpc GetStrategy (GetStrategyRequest) returns (Strategy);
  rpc RunBacktest (RunBacktestRequest) returns (BacktestRun);
  rpc GetBacktestResults (GetBacktestResultsRequest) returns (BacktestResult);
}

service ExecutionService {
  rpc ExecuteTrade (ExecuteTradeRequest) returns (TradeResult);
  rpc GetPosition (GetPositionRequest) returns (Position);
  rpc GetOpenOrders (GetOpenOrdersRequest) returns (OpenOrders);
}
```

---

## WebSocket Events

```yaml
Client → Server:
  subscribe: { channels: ["market_data:RELIANCE", "risk:alerts"] }
  unsubscribe: { channels: ["market_data:RELIANCE"] }

Server → Client:
  market_data: { symbol, timestamp, price, volume, ... }
  risk_alert: { type, severity, message, ... }
  trade_update: { trade_id, status, filled_quantity, ... }
  agent_status: { agent_id, status, current_task, ... }
```

---

---

## Section: API Gateway

### Gateway Architecture

```
Client → API Gateway (Kong/Traefik) → Auth Service → Rate Limiter → Service
         │
         ├── TLS termination
         ├── JWT validation / mTLS handshake
         ├── Rate limit (sliding window)
         ├── RBAC enforcement
         ├── Request routing
         └── Request/response logging (Loki)
```

### Gateway Responsibilities

1. TLS termination (TLS 1.3)
2. JWT validation for humans, mTLS for services and agents
3. Rate limit enforcement (sliding window per client)
4. RBAC check against policy engine
5. Request routing to appropriate service
6. Circuit breaker per upstream service (5 failures → 30s open)
7. Request/response logging for audit

---

## Section: Authentication

### Auth Methods

| Actor | Method | Token Type | Expiry |
|-------|--------|------------|--------|
| Human (dashboard) | OAuth2 + Google/GitHub | JWT | 24h |
| Human (CLI) | API Key | JWT | 90d |
| AI Agent | Agent Identity Token | mTLS + JWT | 1h |
| Service | mTLS | Certificate | 1y |

### Token Format (JWT)

```json
{
  "sub": "user_abc123",
  "role": "researcher",
  "type": "human",
  "iat": 1700000000,
  "exp": 1700086400,
  "jti": "unique_token_id"
}
```

### RBAC Roles

| Role | Permissions |
|------|------------|
| `admin` | Full access, limit changes, user management |
| `researcher` | Read/write hypotheses, strategies, backtests |
| `trader` | Execute trades, read portfolio |
| `viewer` | Read-only dashboard |
| `agent` | Engine-specific scoped access |

---

## Section: Rate Limiting

| Tier | Requests/Min | Burst | Scope |
|------|-------------|-------|-------|
| Human UI | 60 | 10 | Per user |
| CLI | 120 | 20 | Per API key |
| Agent | 300 | 50 | Per agent identity |
| Backtest (async) | 10 | 2 | Per service |

Algorithm: Sliding window log
Response on limit: HTTP 429 + `Retry-After` header

---

## Section: API Versioning

```yaml
scheme: "URL path prefix"
format: "/api/v1/..."
current: "v1"
deprecation_policy: "6 months notice"
sunset_policy: "12 months notice"
```

---

## Section: gRPC Service Definitions (Internal)

### Pattern

```protobuf
service EngineService {
  rpc GetSignals(GetSignalsRequest) returns (GetSignalsResponse);
  rpc Validate(ValidateRequest) returns (ValidateResponse);
  rpc GetStatus(GetStatusRequest) returns (GetStatusResponse);
}

message GetSignalsRequest {
  string strategy_id = 1;
  MarketContext context = 2;
}
```

### When to Use gRPC vs REST vs Event Bus

| Transport | Use For | Example |
|-----------|---------|---------|
| REST | External client API | Dashboard queries |
| gRPC | Internal service sync | Agent queries engine |
| Event Bus | Async actions | Backtest completed |
| WebSocket | Real-time streams | Live price updates |
