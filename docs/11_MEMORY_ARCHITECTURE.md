# QuantLab AI — Memory Architecture

> **How QuantLab AI Remembers**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

QuantLab AI implements a multi-layered memory architecture inspired by human cognitive science. Each layer serves a different purpose, retention period, and access pattern.

---

## Memory Layers

### Layer 1: Working Memory
**Purpose**: Active task context and immediate state
**Storage**: Redis (in-memory)
**Retention**: Session duration (hours)
**Capacity**: ~100KB per session

```
Contents:
- Current task context
- Recent messages
- Active hypothesis state
- Temporary calculations
- Active agent state
```

### Layer 2: Episodic Memory
**Purpose**: Past research sessions and outcomes
**Storage**: PostgreSQL + Qdrant
**Retention**: 30-90 days
**Capacity**: ~10GB

```
Contents:
- Past research sessions
- Backtest results
- Strategy attempts (successful and failed)
- Agent interaction history
- Decision records
```

### Layer 3: Semantic Memory
**Purpose**: Learned concepts and relationships
**Storage**: Qdrant (vector embeddings) + Neo4j (graph)
**Retention**: Permanent (unless explicitly revised)
**Capacity**: ~100GB

```
Contents:
- Market pattern embeddings
- Strategy feature vectors
- Concept relationships
- Causal relationships
- Statistical distributions
```

### Layer 4: Procedural Memory
**Purpose**: How to perform tasks
**Storage**: Code + Documentation
**Retention**: Permanent
**Capacity**: N/A

```
Contents:
- Workflow definitions
- Task execution templates
- Standard operating procedures
- Validation methodologies
- Optimization algorithms
```

### Layer 5: Institutional Memory
**Purpose**: Collective knowledge of the system
**Storage**: Knowledge Graph (Neo4j) + Vector Store (Qdrant)
**Retention**: Permanent
**Capacity**: ~1TB

```
Contents:
- All research findings
- Strategy lineage
- Market regime history
- Agent performance records
- Decision rationale
- Failure analysis
```

### Layer 6: Reflective Memory
**Purpose**: Self-assessment and improvement
**Storage**: PostgreSQL + Qdrant
**Retention**: Permanent
**Capacity**: ~10GB

```
Contents:
- Performance self-assessments
- Improvement suggestions
- Pattern recognition from failures
- Adaptation records
- Learning trajectories
```

---

## Memory Flow

```
Input → Working Memory → Episodic Memory → Semantic Memory
                              ↓
                      Institutional Memory
                              ↓
                     Reflective Memory
                              ↓
                     Procedural Memory
```

### Consolidation Process
1. **Immediate**: Working memory captures current context
2. **Hourly**: Episodic consolidation from working memory
3. **Daily**: Semantic pattern extraction from episodes
4. **Weekly**: Institutional knowledge integration
5. **Monthly**: Reflective analysis and self-improvement

---

## Memory Access Patterns

### Read Priority
| Layer | Latency | Frequency | Consistency |
|-------|---------|-----------|-------------|
| Working | < 1ms | Very High | Strong |
| Episodic | < 10ms | High | Eventual |
| Semantic | < 50ms | Medium | Eventual |
| Procedural | < 100ms | Low | Strong |
| Institutional | < 200ms | Medium | Eventual |
| Reflective | < 500ms | Low | Eventual |

### Write Priority
| Layer | Latency | Durability |
|-------|---------|------------|
| Working | < 1ms | Volatile |
| Episodic | < 50ms | Persistent |
| Semantic | < 100ms | Persistent |
| Institutional | < 200ms | Persistent |
| Reflective | < 500ms | Persistent |

---

## Memory Retrieval API

```python
# Working Memory
store_working(key, value, ttl=3600)
get_working(key)
clear_working_session(session_id)

# Episodic Memory
store_episode(episode_data)
query_episodes(similar_to, timeframe, limit=10)
get_episode(episode_id)

# Semantic Memory
store_concept(concept_data)
query_similar(query_embedding, limit=5)
get_relationships(concept_id)

# Institutional Memory
store_knowledge(knowledge_unit)
query_knowledge(query, filters)
get_lineage(entity_id)
```

---

## Eviction Policies

| Layer | Policy | Trigger |
|-------|--------|---------|
| Working | TTL-based | 1 hour inactivity |
| Episodic | Age + importance | 90 days / low importance |
| Semantic | Importance-based | Never evict important concepts |
| Institutional | Never evict | N/A |
| Reflective | Compression | Monthly summarization |
