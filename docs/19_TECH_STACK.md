# QuantLab AI — Tech Stack

> **Technology Choices**  
> Version 1.0 | Last Updated: July 2026

---

## Technology Radar

### Core Languages
| Language | Version | Usage | Rationale |
|----------|---------|-------|-----------|
| Python | 3.13+ | Primary backend, data analysis, ML | Best ecosystem for quant finance |
| TypeScript | 5.x | Dashboard, CLI | Type safety for UI |
| SQL | - | Database queries | Standard |
| YAML/JSON | - | Configuration, serialization | Standard |

### Backend Frameworks
| Framework | Version | Usage | Rationale |
|-----------|---------|-------|-----------|
| FastAPI | 0.115+ | REST API | Async, fast, great DX |
| Pydantic | 2.x | Data validation | Type safety, serialization |
| SQLAlchemy | 2.0+ | ORM | Mature, async support |
| Alembic | 1.13+ | Migrations | Standard for SQLAlchemy |
| LangGraph | 0.2+ | Agent orchestration | Graph-based workflows |
| PydanticAI | 0.1+ | AI agent framework | Pydantic-native agents |

### Data & ML Stack
| Library | Usage | Rationale |
|---------|-------|-----------|
| pandas | Data manipulation | Industry standard |
| numpy | Numerical computing | Foundation for everything |
| scipy | Statistical tests | Comprehensive stats |
| scikit-learn | ML models | Standard ML toolkit |
| statsmodels | Time series, stats | Statistical modeling |
| backtesting.py | Backtesting | Clean, well-designed |
| vectorbt | Vectorized backtesting | Fast, portfolio-level |
| xgboost | Gradient boosting | Best for tabular data |
| pytorch | Deep learning | Flexible, research-grade |
| optuna | Hyperparameter optimization | Efficient search |

### Infrastructure
| Tool | Usage | Rationale |
|------|-------|-----------|
| Docker | Containerization | Universal, standard |
| Docker Compose | Local orchestration | Simple multi-service setup |
| PostgreSQL | Primary database | Mature, reliable, extensible |
| Qdrant | Vector database | Fast, efficient, open source |
| Neo4j | Graph database | Knowledge graph |
| Redis | Cache, pub-sub | Fast, battle-tested |
| MinIO | Object storage | S3-compatible, self-hosted |
| RabbitMQ | Message broker | Reliable, feature-rich |

### Monitoring
| Tool | Usage | Rationale |
|------|-------|-----------|
| Prometheus | Metrics collection | Industry standard |
| Grafana | Visualization | Flexible dashboards |
| Loki | Log aggregation | Lightweight, integrated |
| Tempo | Distributed tracing | OpenTelemetry native |

### Frontend
| Tool | Usage | Rationale |
|------|-------|-----------|
| Streamlit | Research dashboard | Fast prototyping |
| Next.js (future) | Production dashboard | Full-featured |
| Plotly/Dash | Interactive charts | Rich visualization |

### AI/LLM
| Provider | Usage | Rationale |
|----------|-------|-----------|
| OpenAI | Primary LLM (GPT-4o) | Best general performance |
| Anthropic | Secondary LLM (Claude) | Strong reasoning |
| Ollama | Local models | Privacy, offline |
| OpenRouter | Fallback routing | Provider diversity |
| LangChain/LangGraph | Agent framework | Orchestration |

### Development Tools
| Tool | Usage |
|------|-------|
| Poetry | Python package management |
| mypy | Static type checking |
| ruff | Linting and formatting |
| pytest | Testing framework |
| pre-commit | Git hooks |
| make | Task automation |

---

## Decision Records

### Why Python 3.13+?
- Best ecosystem for quantitative finance
- Async support for real-time data
- Rich ML/data science ecosystem
- Strong typing via mypy

### Why FastAPI over Django/Flask?
- Native async support
- Automatic OpenAPI docs
- Pydantic integration
- Excellent performance

### Why PostgreSQL over MySQL?
- Better analytical queries (JSONB, window functions)
- Extensions (TimescaleDB for time-series)
- Better concurrency handling
- Mature and reliable

### Why Qdrant over Pinecone/Weaviate?
- Self-hosted (no vendor lock-in)
- Excellent performance
- Open source
- Built for Rust (safety, speed)

### Why Neo4j for Knowledge Graph?
- Mature graph database
- Powerful Cypher query language
- Excellent Python driver
- ACID compliance

### Why LangGraph over CrewAI/AutoGen?
- Graph-based workflow (more flexible)
- LangChain ecosystem integration
- Better debugging and observability
- Pythonic design

---

## Version Policy

| Category | Update Cadence | Major Version Policy |
|----------|---------------|---------------------|
| Languages | Latest stable | Update within 6 months |
| Frameworks | Minor updates | Major versions: 6-month review |
| Libraries | As needed | Evaluate on major release |
| Infrastructure | Security patches immediately | Major: 3-month review |

---

## Compatibility Matrix

```
Python 3.13+  ──► FastAPI 0.115+ ──► Pydantic 2.x
                                   ──► SQLAlchemy 2.0+
                                   ──► LangGraph 0.2+

PostgreSQL 17 ──► SQLAlchemy 2.0+ ──► Alembic 1.13+

Docker 24+    ──► Docker Compose 2.x
```
