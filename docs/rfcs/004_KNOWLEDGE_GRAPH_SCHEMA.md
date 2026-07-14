# RFC-004: Knowledge Graph Schema Definition

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

Doc 12 (Knowledge Graph Spec) describes what the graph *does* and doc 35 lists node/edge types, but there is no formal Neo4j schema — no node properties, no edge properties, no indexes, no constraints. Doc 15 (Database Schema) covers PostgreSQL only, leaving Neo4j unmodeled.

Without a schema, the knowledge graph risks drift — different agents storing inconsistent data shapes.

## Proposed Neo4j Schema

### Nodes

```
Hypothesis {
  id: string PK
  title: string
  description: string
  status: string  // proposed | testing | confirmed | rejected
  confidence: float
  created_at: datetime
  tested_at: datetime?
  keywords: list<string>
}

Strategy {
  id: string PK
  name: string
  version: string  // semver
  dsl: string       // YAML definition
  status: string    // draft | backtesting | validating | paper | live | retired
  sharpe: float?
  max_drawdown: float?
  created_at: datetime
}

Experiment {
  id: string PK
  type: string        // backtest | paper | live
  config: json
  result_sharpe: float?
  result_drawdown: float?
  result_trades: int?
  started_at: datetime
  completed_at: datetime?
}

MarketRegime {
  id: string PK
  name: string        // trending | ranging | volatile | crisis
  start_date: date
  end_date: date?
  assets: list<string>
}

Instrument {
  id: string PK
  symbol: string
  exchange: string
  asset_class: string
  sector: string?
  market_cap: string?
}

ResearchSession {
  id: string PK
  goal: string
  findings: text
  started_at: datetime
  concluded_at: datetime?
}

RiskEvent {
  id: string PK
  type: string
  severity: string
  description: text
  loss_amount: float?
  occurred_at: datetime
}

DecisionRecord {
  id: string PK
  title: string
  decision: text
  rationale: text
  alternatives: list<string>
  decided_by: string
  decided_at: datetime
}
```

### Edges

| Type | Source | Target | Properties |
|------|--------|--------|------------|
| `TESTS` | Hypothesis | Strategy | confidence: float, created_at |
| `VALIDATED_BY` | Strategy | Experiment | result: string, accuracy: float |
| `OCCURS_IN` | Experiment | MarketRegime | fit_score: float |
| `TRADES` | Strategy | Instrument | direction: string, weight: float |
| `CONTRADICTS` | Hypothesis | Hypothesis | confidence: float, discovered_at |
| `CAUSES` | RiskEvent | — | loss_amount: float, recovery_days: int |
| `DEPENDS_ON` | Strategy | DataSource | required: bool |
| `DISCOVERED_IN` | Strategy | ResearchSession | relevance: float |
| `DECIDED_BY` | DecisionRecord | Agent | authority: string |
| `RELATES_TO` | (any) | (any) | strength: float |

### Indexes & Constraints

```cypher
CREATE CONSTRAINT hypothesis_id IF NOT EXISTS FOR (h:Hypothesis) REQUIRE h.id IS UNIQUE
CREATE CONSTRAINT strategy_id IF NOT EXISTS FOR (s:Strategy) REQUIRE s.id IS UNIQUE
CREATE CONSTRAINT instrument_id IF NOT EXISTS FOR (i:Instrument) REQUIRE i.id IS UNIQUE

CREATE INDEX hypothesis_status IF NOT EXISTS FOR (h:Hypothesis) ON (h.status)
CREATE INDEX strategy_status IF NOT EXISTS FOR (s:Strategy) ON (s.status)
CREATE INDEX strategy_sharpe IF NOT EXISTS FOR (s:Strategy) ON (s.sharpe)
```

### Changes Required

| Document | Change |
|----------|--------|
| doc 12 | Add full schema section with all nodes, edges, properties |
| doc 15 | Add Neo4j subsection referencing doc 12 schema |
| doc 35 | Update Section V to reference schema |

## Action

- [ ] Add neo4j schema to doc 12
- [ ] Add Neo4j subsection to doc 15
