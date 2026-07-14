# QuantLab AI — Knowledge Graph Specification

> **Connected Knowledge**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Knowledge Graph is QuantLab AI's institutional memory — a connected representation of everything the system knows about markets, strategies, hypotheses, and their relationships.

---

## Graph Structure

### Nodes

#### Entity Types

| Type | Description | Properties |
|------|-------------|------------|
| Hypothesis | Market hypothesis | id, title, description, status, created_at, confidence |
| Strategy | Trading strategy | id, name, type, parameters, status, version |
| Market | Market/Instrument | id, symbol, exchange, asset_class, sector |
| Regime | Market regime | id, type, start_date, end_date, characteristics |
| Research | Research session | id, goal, methodology, findings, conclusion |
| Agent | AI agent | id, role, capabilities, performance_metrics |
| DataSource | Data source | id, name, type, frequency, reliability_score |
| Indicator | Technical indicator | id, name, parameters, category |
| Event | Market event | id, type, timestamp, impact, description |
| Risk | Risk metric | id, type, value, threshold, timestamp |
| Portfolio | Portfolio allocation | id, name, composition, performance |
| Experiment | Research experiment | id, design, parameters, results, reproducibility |

### Edges

#### Relationship Types

| Type | Description | Weighted |
|------|-------------|----------|
| TESTS | Hypothesis tests strategy | Yes |
| VALIDATED_BY | Strategy validated by experiment | No |
| OCCURS_IN | Strategy operates in market | No |
| AFFECTED_BY | Performance affected by regime | Yes |
| DISCOVERED_IN | Hypothesis discovered in research | No |
| USES | Strategy uses indicator | No |
| DEPENDS_ON | Strategy depends on data source | No |
| PRODUCES | Experiment produces result | No |
| RELATES_TO | Entity conceptually related | Yes |
| PRECEDES | Temporal ordering | No |
| CAUSES | Causal relationship | Yes |
| CONTRADICTS | Contradictory findings | No |

---

## Query Patterns

### Find Related Strategies
```cypher
MATCH (h:Hypothesis {id: 'hyp_015'})-[:TESTS]->(s:Strategy)
RETURN s.name, s.sharpe_ratio, s.status
ORDER BY s.sharpe_ratio DESC
```

### Find Strategies for Market
```cypher
MATCH (s:Strategy)-[:OCCURS_IN]->(m:Market {symbol: 'RELIANCE'})
WHERE s.status = 'active'
RETURN s.name, s.sharpe_ratio, s.max_drawdown
```

### Find Causal Chain
```cypher
MATCH path = (h:Hypothesis)-[:CAUSES*1..3]->(result)
WHERE h.id = 'hyp_015'
RETURN path
```

### Find Contradicting Research
```cypher
MATCH (r1:Research)-[:CONTRADICTS]->(r2:Research)
RETURN r1.title, r2.title, r1.confidence, r2.confidence
```

---

## Knowledge Graph API

```python
# Node operations
create_node(entity_type, properties)
get_node(node_id)
update_node(node_id, properties)
delete_node(node_id)
search_nodes(query, filters, limit=10)

# Edge operations
create_edge(source_id, target_id, relationship_type, properties)
get_edges(node_id, direction='both', relationship_type=None)
delete_edge(edge_id)

# Query operations
k_hop_query(node_id, depth=2, relationship_type=None)
path_query(start_id, end_id, max_depth=5)
similarity_query(embedding, entity_type=None, limit=5)
```

---

## Integration With Other Systems

### With Memory Architecture
- Knowledge Graph = Institutional Memory (Layer 5)
- Episodic Memory feeds new nodes
- Working Memory queries the graph for context

### With AI Agents
- Agents read context from the graph
- Agents write findings to the graph
- Graph edges feed agent reasoning

### With Research Engine
- Hypotheses become nodes
- Experiments produce edges
- Results update node properties

---

## Contradiction Detection

The Knowledge Graph includes a contradiction detection engine:

```python
def detect_contradictions(new_finding):
    existing = query_similar(new_finding)
    contradictions = []
    for finding in existing:
        if statistically_contradicts(new_finding, finding):
            create_edge(
                new_finding.id,
                finding.id,
                "CONTRADICTS",
                {"confidence": compute_contradiction_score()}
            )
            contradictions.append(finding)
    return contradictions
```

---

## Graph Maintenance

### Indexing
| Index Type | Target | Update Frequency |
|------------|--------|-----------------|
| Node ID | All nodes | Real-time |
| Property | Frequently queried properties | Per batch |
| Embedding | Node embeddings for similarity | Daily |
| Full-text | Text properties | Weekly |

### Archival
- Nodes inactive > 1 year → Archived to cold storage
- Confidence < 0.3 → Flagged for review
- Orphaned nodes → Reconnected or archived

---

## Neo4j Schema

### Nodes

```
Hypothesis {
  id: string PK
  title: string
  description: string
  status: string         // proposed | testing | confirmed | rejected
  confidence: float
  created_at: datetime
  tested_at: datetime?
  keywords: list<string>
}

Strategy {
  id: string PK
  name: string
  version: string        // semver
  dsl: string            // YAML definition
  status: string         // draft | backtesting | validating | paper | live | retired
  sharpe: float?
  max_drawdown: float?
  created_at: datetime
}

Experiment {
  id: string PK
  type: string           // backtest | paper | live
  config: json
  result_sharpe: float?
  result_drawdown: float?
  result_trades: int?
  started_at: datetime
  completed_at: datetime?
}

MarketRegime {
  id: string PK
  name: string           // trending | ranging | volatile | crisis
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
CREATE CONSTRAINT hypothesis_id IF NOT EXISTS
  FOR (h:Hypothesis) REQUIRE h.id IS UNIQUE;
CREATE CONSTRAINT strategy_id IF NOT EXISTS
  FOR (s:Strategy) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT instrument_id IF NOT EXISTS
  FOR (i:Instrument) REQUIRE i.id IS UNIQUE;

CREATE INDEX hypothesis_status IF NOT EXISTS
  FOR (h:Hypothesis) ON (h.status);
CREATE INDEX strategy_status IF NOT EXISTS
  FOR (s:Strategy) ON (s.status);
CREATE INDEX strategy_sharpe IF NOT EXISTS
  FOR (s:Strategy) ON (s.sharpe);
```
