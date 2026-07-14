# QuantLab AI — System Architecture

> **The Blueprint**  
> Version 1.0 | Last Updated: July 2026

---

## Architecture Philosophy

QuantLab AI follows **Clean Architecture** principles with **Domain-Driven Design**:

1. **Independence** — The domain layer depends on nothing external
2. **Testability** — Every layer can be tested in isolation
3. **Replaceability** — Any external dependency can be swapped
4. **Understandability** — The architecture can be grasped in one sitting

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│                   Apps Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Dashboard │  │   CLI    │  │   API    │       │
│  │(Streamlit│  │(Click/   │  │(FastAPI) │       │
│  │ /Next.js)│  │ Typer)   │  │          │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       └─────────────┼──────────────┘              │
└─────────────────────┼────────────────────────────┘
                      │
┌─────────────────────┼────────────────────────────┐
│               Service Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Research │  │ Strategy │  │ Backtest │        │
│  │ Engine   │  │ Engine   │  │ Engine   │        │
│  ├──────────┤  ├──────────┤  ├──────────┤        │
│  │Validation│  │   Risk   │  │Portfolio │        │
│  │ Engine   │  │ Engine   │  │ Engine   │        │
│  ├──────────┤  ├──────────┤  ├──────────┤        │
│  │ Execution│  │   Data   │  │    ML    │        │
│  │ Engine   │  │ Engine   │  │ Engine   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
└─────────────────────┼────────────────────────────┘
                      │
┌─────────────────────┼────────────────────────────┐
│                Package Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Core    │  │  Market  │  │Indicators│        │
│  ├──────────┤  ├──────────┤  ├──────────┤        │
│  │Statistics│  │Backtest. │  │   Risk   │        │
│  │          │  │   py     │  │  Models  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
└─────────────────────┼────────────────────────────┘
                      │
┌─────────────────────┼────────────────────────────┐
│              Infrastructure Layer                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │PostgreSQL│  │  Qdrant  │  │  Neo4j   │        │
│  │(Relational│ │(Vector)  │  │ (Graph)  │        │
│  ├──────────┤  ├──────────┤  ├──────────┤        │
│  │  Redis   │  │   S3/   │  │  Docker  │        │
│  │ (Cache)  │  │ MinIO   │  │ (Container│        │
│  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────┘
```

---

## Layer Architecture

### 1. Domain Layer (packages/core)
- Enterprise business rules
- Domain entities and value objects
- Repository interfaces (not implementations)
- No external dependencies

### 2. Application Layer (services/*)
- Use cases and business workflows
- Orchestration of domain objects
- Service interfaces
- Depends only on domain layer

### 3. Interface Layer (apps/*, packages/broker-api)
- Controllers, presenters, serializers
- API endpoints
- CLI commands
- Dashboard components

### 4. Infrastructure Layer (packages/*, plugins/*)
- Database implementations
- External service adapters
- Broker integrations
- File system access

---

## Data Flow

### Research Flow
```
Hypothesis → Data Collection → Feature Engineering →
Strategy Design → Backtest → Validation →
Optimization → Walk-Forward → Paper Trade → Deploy
```

### Trading Flow
```
Market Data → Signal Generation → Risk Check →
Portfolio Check → Order Generation → Broker Gateway →
Execution → Settlement → P&L Attribution
```

---

## Event-Driven Architecture

Services communicate through an event bus:
- **Commands** — Do this (point-to-point)
- **Events** — This happened (pub-sub)
- **Queries** — What is the state? (request-response)

### Key Events
| Event | Publisher | Subscribers |
|-------|-----------|-------------|
| HypothesisCreated | ResearchEngine | StrategyEngine, KnowledgeEngine |
| StrategyReady | StrategyEngine | BacktestEngine, ValidationEngine |
| BacktestComplete | BacktestEngine | ValidationEngine, RiskEngine |
| ValidationPassed | ValidationEngine | PortfolioEngine, ExecutionEngine |
| RiskLimitBreached | RiskEngine | ExecutionEngine, Alerting |
| TradeExecuted | ExecutionEngine | PortfolioEngine, RiskEngine, KnowledgeEngine |

---

## Service Communication

```
┌─────────┐     Event Bus     ┌─────────┐
│ Service ├──────────────────►│ Service │
│   A     │                   │   B     │
└────┬────┘                   └─────────┘
     │
     │ gRPC (sync) / Redis Pub-Sub (async)
     │
┌────▼────────────────────────────────────┐
│           Message Queue (RabbitMQ)       │
└─────────────────────────────────────────┘
```

---

## Database Strategy

| Database | Purpose | Data Types |
|----------|---------|------------|
| PostgreSQL | Primary store | Market data, trades, accounts, users |
| Qdrant | Vector search | Strategy embeddings, document embeddings |
| Neo4j | Knowledge graph | Entity relationships, research lineage |
| Redis | Cache, pub-sub | Market data cache, session state |
| MinIO/S3 | Object storage | Historical data files, model artifacts |

---

## Scalability Model

### Vertical (V0-V1)
- Monolithic FastAPI server
- PostgreSQL single instance
- Background task workers
- Docker Compose deployment

### Horizontal (V2+)
- Microservices decomposition
- Read replicas for PostgreSQL
- Qdrant cluster for vector search
- Kubernetes orchestration
- Event-driven scaling

---

## Architecture Decision Records

All significant architectural decisions must be documented as ADRs in `docs/architecture/decisions/`.
