# QuantLab AI — Database Schema

> **Data Storage Design**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

QuantLab AI uses a polyglot persistence approach with PostgreSQL as the primary relational store, Qdrant for vector search, and Neo4j for the knowledge graph.

---

## PostgreSQL Schema

### Entity Relationship Overview

```
Markets ──1:N──> MarketData
Users ──1:N──> ResearchSessions
ResearchSessions ──1:N──> Hypotheses
Hypotheses ──1:N──> Strategies
Strategies ──1:N──> BacktestResults
Strategies ──1:N──> Trades
Portfolios ──1:N──> Allocations
Agents ──1:N──> AgentTasks
```

### Tables

#### markets
```sql
CREATE TABLE markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    asset_class VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(100),
    isin VARCHAR(20),
    lot_size INTEGER DEFAULT 1,
    tick_size DECIMAL(10,4),
    currency VARCHAR(3) DEFAULT 'INR',
    status VARCHAR(20) DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, exchange)
);
```

#### market_data
```sql
CREATE TABLE market_data (
    id BIGSERIAL PRIMARY KEY,
    market_id UUID REFERENCES markets(id),
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(20,4) NOT NULL,
    high DECIMAL(20,4) NOT NULL,
    low DECIMAL(20,4) NOT NULL,
    close DECIMAL(20,4) NOT NULL,
    volume BIGINT NOT NULL,
    vwap DECIMAL(20,4),
    trades_count INTEGER,
    interval VARCHAR(10) NOT NULL,
    source VARCHAR(50),
    quality_score DECIMAL(3,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(market_id, timestamp, interval)
) PARTITION BY RANGE (timestamp);
```

#### hypotheses
```sql
CREATE TABLE hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    status VARCHAR(20) DEFAULT 'draft',
    confidence DECIMAL(3,2),
    market_conditions JSONB,
    methodology TEXT,
    assumptions JSONB,
    risk_factors JSONB,
    literature_references JSONB,
    created_by VARCHAR(100),
    session_id UUID REFERENCES research_sessions(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### strategies
```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    hypothesis_id UUID REFERENCES hypotheses(id),
    type VARCHAR(50) NOT NULL,
    description TEXT,
    parameters JSONB NOT NULL,
    entry_rules JSONB,
    exit_rules JSONB,
    position_sizing JSONB,
    risk_rules JSONB,
    markets JSONB,
    status VARCHAR(20) DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    lineage UUID[],  -- Array of parent strategy IDs
    tags TEXT[],
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### backtest_results
```sql
CREATE TABLE backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategies(id),
    run_id UUID NOT NULL,
    status VARCHAR(20) DEFAULT 'running',
    
    -- Performance Metrics
    total_return DECIMAL(10,4),
    annualized_return DECIMAL(10,4),
    volatility DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    calmar_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    win_rate DECIMAL(5,2),
    profit_factor DECIMAL(10,4),
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    avg_win DECIMAL(20,4),
    avg_loss DECIMAL(20,4),
    
    -- Parameters
    parameters JSONB,
    timeframe VARCHAR(20),
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    initial_capital DECIMAL(20,4),
    
    -- Execution
    execution_time INTERVAL,
    engine_version VARCHAR(20),
    
    -- Metadata
    tags TEXT[],
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### trades
```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategies(id),
    portfolio_id UUID REFERENCES portfolios(id),
    market_id UUID REFERENCES markets(id),
    
    -- Trade Details
    direction VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20,4) NOT NULL,
    exit_price DECIMAL(20,4),
    quantity INTEGER NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    
    -- P&L
    gross_pnl DECIMAL(20,4),
    net_pnl DECIMAL(20,4),
    commission DECIMAL(20,4),
    slippage DECIMAL(20,4),
    returns DECIMAL(10,4),
    
    -- Classification
    trade_type VARCHAR(20),  -- intraday, swing, position
    signal_id UUID,
    exit_reason VARCHAR(50),
    
    -- Backtest vs Live
    environment VARCHAR(20) DEFAULT 'backtest',  -- backtest, paper, live
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### portfolios
```sql
CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    strategy_allocations JSONB NOT NULL,
    initial_capital DECIMAL(20,4),
    current_value DECIMAL(20,4),
    risk_parameters JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### agents
```sql
CREATE TABLE agents (
    id VARCHAR(100) PRIMARY KEY,
    role VARCHAR(100) NOT NULL,
    level VARCHAR(10),
    capabilities JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'idle',
    current_load DECIMAL(3,2) DEFAULT 0,
    max_load INTEGER DEFAULT 5,
    performance_metrics JSONB,
    metadata JSONB,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### agent_tasks
```sql
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID,
    agent_id VARCHAR(100) REFERENCES agents(id),
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'normal',
    input JSONB,
    output JSONB,
    dependencies JSONB,
    deadline TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_log TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### events
```sql
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source JSONB,
    correlation_id UUID,
    causation_id UUID,
    priority VARCHAR(20),
    payload JSONB,
    metadata JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_correlation ON events(correlation_id);
CREATE INDEX idx_events_timestamp ON events(timestamp);
```

---

## Qdrant Collections

### strategy_embeddings
```yaml
collection: strategy_embeddings
vector_size: 384
distance: Cosine
payload:
  - strategy_id
  - strategy_name
  - strategy_type
  - performance_metrics
  - tags
```

### hypothesis_embeddings
```yaml
collection: hypothesis_embeddings
vector_size: 384
distance: Cosine
payload:
  - hypothesis_id
  - title
  - status
  - confidence
  - category
```

### knowledge_embeddings
```yaml
collection: knowledge_embeddings
vector_size: 384
distance: Cosine
payload:
  - entity_id
  - entity_type
  - entity_name
  - description
  - tags
```

---

## Neo4j Graph Schema

### Node Labels
```
Hypothesis, Strategy, Market, Regime, Research,
Agent, DataSource, Indicator, Event, Risk, Portfolio, Experiment
```

### Relationship Types
```
TESTS, VALIDATED_BY, OCCURS_IN, AFFECTED_BY,
DISCOVERED_IN, USES, DEPENDS_ON, PRODUCES,
RELATES_TO, PRECEDES, CAUSES, CONTRADICTS
```

---

## Partitioning Strategy

| Table | Partition Key | Interval | Retention |
|-------|--------------|----------|-----------|
| market_data | timestamp | Monthly | 10 years |
| trades | entry_time | Monthly | 5 years |
| events | timestamp | Weekly | 90 days |
| backtest_results | created_at | Quarterly | 2 years |

---

## Indexing Strategy

### Primary Indexes
- All primary keys: B-tree
- All foreign keys: B-tree
- High-frequency query columns: B-tree
- JSONB queries: GIN

### Time-Series Indexes
- market_data (market_id, timestamp): B-tree composite
- market_data (timestamp DESC): BRIN for partitioning
- trades (entry_time, strategy_id): B-tree composite
