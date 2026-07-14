# QuantLab AI — Repository Structure

> **How the Code Is Organized**  
> Version 1.0 | Last Updated: July 2026

---

## Repository Layout

```
quantlab-ai/
├── apps/                          # Application entry points
│   ├── dashboard/                 # Streamlit dashboard
│   │   ├── pages/                 # Dashboard pages
│   │   ├── components/            # Reusable dashboard components
│   │   └── app.py                 # Main dashboard entry
│   │
│   ├── cli/                       # Command-line interface
│   │   ├── commands/              # CLI command groups
│   │   └── main.py                # CLI entry point
│   │
│   └── api/                       # FastAPI server
│       ├── routes/                # API route handlers
│       ├── middleware/            # API middleware
│       └── main.py                # FastAPI app entry
│
├── services/                      # Business logic services
│   ├── data-engine/               # Data acquisition and processing
│   ├── research-engine/           # Hypothesis management
│   ├── strategy-engine/           # Strategy design and management
│   ├── backtest-engine/           # Historical simulation
│   ├── optimization-engine/       # Parameter optimization
│   ├── validation-engine/         # Statistical validation
│   ├── risk-engine/               # Risk calculation and monitoring
│   ├── portfolio-engine/          # Portfolio management
│   ├── execution-engine/          # Trade execution
│   ├── broker-gateway/            # Broker abstraction
│   └── ml-engine/                 # Machine Learning
│
├── packages/                      # Shared libraries
│   ├── core/                      # Domain models, base classes
│   │   ├── models/                # Domain entities
│   │   ├── value_objects/         # Value objects
│   │   ├── interfaces/            # Abstract interfaces
│   │   └── exceptions/            # Domain exceptions
│   │
│   ├── market/                    # Market data types
│   │   ├── instruments/           # Instrument definitions
│   │   ├── data_types/            # OHLCV, tick, order book
│   │   └── enums/                 # Market enums
│   │
│   ├── indicators/                # Technical indicators
│   │   ├── trend/                 # Trend indicators
│   │   ├── momentum/              # Momentum indicators
│   │   ├── volatility/            # Volatility indicators
│   │   └── volume/                # Volume indicators
│   │
│   ├── statistics/                # Statistical methods
│   │   ├── tests/                 # Statistical tests
│   │   ├── distributions/         # Probability distributions
│   │   └── metrics/               # Performance metrics
│   │
│   ├── backtesting/               # Backtesting core
│   │   ├── engine/                # Backtest engine
│   │   ├── metrics/               # Performance metrics
│   │   └── reporting/             # Results reporting
│   │
│   ├── risk/                      # Risk models
│   │   ├── metrics/               # Risk metrics
│   │   ├── models/                # Risk models
│   │   └── stress/                # Stress testing
│   │
│   └── broker-api/                # Broker abstraction layer
│       ├── base/                  # Abstract broker interface
│       ├── models/                # Order, position models
│       └── exceptions/            # Broker exceptions
│
├── agents/                        # AI agent definitions
│   ├── researcher/                # Research Scientist agent
│   ├── strategist/                # Strategy Architect agent
│   ├── validator/                 # Validation Scientist agent
│   ├── risk-manager/              # Risk Manager agent
│   └── portfolio-manager/         # Portfolio Manager agent
│
├── plugins/                       # Plugin implementations
│   ├── brokers/                   # Broker adapters
│   │   ├── zerodha/
│   │   ├── angel-one/
│   │   ├── alpaca/
│   │   └── ibkr/
│   │
│   ├── data-sources/              # Data source adapters
│   │   ├── nse/
│   │   └── yahoo-finance/
│   │
│   ├── indicators/                # Indicator plugins
│   └── strategies/                # Strategy plugins
│
├── config/                        # Configuration files
│   ├── default.yaml
│   ├── development.yaml
│   ├── staging.yaml
│   ├── production.yaml
│   └── schema.yaml
│
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (mirrors src/)
│   ├── integration/               # Integration tests
│   ├── e2e/                       # End-to-end tests
│   └── ai/                        # AI agent tests
│
├── docs/                          # Documentation
│   ├── architecture/              # Architecture docs
│   │   └── decisions/             # ADRs
│   ├── guides/                    # User guides
│   ├── api/                       # API documentation
│   └── specs/                     # Specification docs
│
├── scripts/                       # Utility scripts
│   ├── setup.sh                   # Development setup
│   ├── migrate.sh                 # Database migrations
│   └── seed.sh                    # Seed data
│
├── docker/                        # Docker files
│   ├── Dockerfile                 # Main Dockerfile
│   ├── docker-compose.yml         # Development composition
│   └── docker-compose.prod.yml    # Production composition
│
├── kubernetes/                    # K8s manifests (future)
│   ├── services/
│   └── config/
│
├── .github/                       # GitHub configuration
│   └── workflows/                 # CI/CD pipelines
│
├── pyproject.toml                 # Python project configuration
├── poetry.lock                    # Poetry lock file
├── Makefile                       # Task automation
├── README.md                      # Project overview
├── CONTRIBUTING.md                # Contribution guide
├── LICENSE                        # License file
└── .gitignore                     # Git ignore
```

---

## Package Dependencies

```
                    ┌──────────┐
                    │   apps   │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ services │
                    └────┬─────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
     ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐
     │ packages│  │  agents   │  │ plugins │
     └────┬────┘  └───────────┘  └────┬────┘
          │                           │
          └───────────┬───────────────┘
                      │
                 ┌────▼────┐
                 │  core   │
                 └─────────┘
```

### Dependency Rules
- `apps/*` may depend on `services/*`, `packages/*`
- `services/*` may depend on `packages/*`, `agents/*`
- `packages/*` may depend on `packages/core` only
- `agents/*` may depend on `packages/*`
- `plugins/*` depend on `packages/broker-api` or `packages/core`
- `packages/core` has ZERO external dependencies
- No circular dependencies allowed

---

## File Naming Conventions

| Directory | Convention | Example |
|-----------|-----------|---------|
| services/* | snake_case | data_engine.py |
| packages/* | snake_case | market_data.py |
| agents/* | snake_case | research_scientist.py |
| plugins/* | kebab-case | zerodha-broker/ |
| apps/* | kebab-case | data-pipeline.ts |
| tests/* | snake_case | test_data_engine.py |
