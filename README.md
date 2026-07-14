# QuantLab AI

**AI-augmented quantitative research operating system**

QuantLab AI is a platform for discovering, validating, and deploying statistically robust trading strategies through rigorous scientific methodology amplified by artificial intelligence.

## Philosophy

- **Science First** — Every trade is an experiment, every strategy is a hypothesis
- **Truth Over Profit** — Correct methodology > short-term gains
- **Reproducibility** — Every result must be reproducible
- **Modularity** — Replace any component without rebuilding the whole
- **Rigor Over Speed** — A single validated strategy > 1000 untested ideas

## Architecture

```
apps/           — Application entry points (API, CLI, Dashboard)
services/       — Business logic engines
packages/       — Shared libraries
agents/         — AI agent definitions
plugins/        — Extensible plugin system
docs/           — Full specification (30 documents)
```

## Quick Start

```bash
# Prerequisites: Python 3.13+, Poetry, Docker

# Clone the repository
git clone https://github.com/SatyaNagesh/Trading-Bot.git
cd Trading-Bot

# Install dependencies
poetry install

# Start infrastructure
docker compose -f docker/docker-compose.yml up -d

# Run API server
poetry run uvicorn apps.api.main:app --reload --port 8000
```

## Documentation

All 30 specification documents are in `docs/`:

| # | Document | Description |
|---|----------|-------------|
| 00 | Project Constitution | Supreme law of QuantLab AI |
| 01 | Project Manifesto | Who we are, what we build |
| 02 | Product Vision | Where we're going |
| 03 | System Architecture | The blueprint |
| 04 | Decision Framework | How we make choices |
| 05 | Engineering Standards | Rules of the road |
| 06 | Organizational Chart | AI agent organization |
| 07 | AI Agent Constitution | Rules for AI agents |
| 08 | Agent Specifications | Detailed agent definitions |
| 09 | Agent Communication Protocol | How agents talk |
| 10 | Task Orchestration Engine | How work gets done |
| 11 | Memory Architecture | How we remember |
| 12 | Knowledge Graph Spec | Connected knowledge |
| 13 | Workflow Engine | Standard procedures |
| 14 | Event Bus Spec | The nervous system |
| 15 | Database Schema | Data storage design |
| 16 | API Specification | How to talk to the system |
| 17 | Plugin System | Extending the platform |
| 18 | Configuration Standard | How we configure |
| 19 | Tech Stack | Technology choices |
| 20 | Repository Structure | Code organization |
| 21 | Coding Standards | How we write code |
| 22 | Testing Strategy | How we ensure quality |
| 23 | CI/CD Pipeline | Automated quality gates |
| 24 | Deployment Architecture | Where the system lives |
| 25 | Observability | Seeing the system |
| 26 | Security Architecture | Keeping it safe |
| 27 | MLOps Architecture | ML operations |
| 28 | Broker Integration | Connecting to markets |
| 29 | Data Pipeline | Data flow |
| 30 | Research Engine | The scientific heart |

## License

MIT
