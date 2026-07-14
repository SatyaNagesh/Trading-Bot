# QuantLab AI — Coding Standards

> **How We Write Code**  
> Version 1.0 | Last Updated: July 2026

---

## Python Standards

### Style Guide
QuantLab AI follows PEP 8 with the following additions:
- Line length: 100 characters (not 79)
- Quotes: Double quotes for strings, single quotes for short non-string literals
- Imports: `isort` with `black` compatible profile
- Type hints: Required for all public functions

### Type Annotations
```python
from typing import Optional, List, Dict, Tuple, Protocol
from datetime import datetime
from decimal import Decimal

def calculate_sharpe(
    returns: List[Decimal],
    risk_free_rate: Decimal = Decimal("0.05"),
    periods_per_year: int = 252
) -> Decimal:
    """Calculate Sharpe ratio from return series."""
    ...
```

### Error Handling
```python
# Good - Specific exception types
class InsufficientDataError(QuantLabError):
    """Raised when data doesn't meet minimum requirements."""

def validate_market_data(data: pd.DataFrame) -> None:
    if len(data) < MIN_DATA_POINTS:
        raise InsufficientDataError(
            f"Need {MIN_DATA_POINTS} points, got {len(data)}"
        )

# Avoid - Bare exceptions
try:
    process_data()
except Exception:  # Bad
    pass
```

### Logging
```python
import structlog
logger = structlog.get_logger()

# Good - Structured logging with context
logger.info("backtest_started", 
    strategy_id=strategy.id,
    parameters=strategy.parameters,
    data_points=len(data)
)

# Avoid - String formatting in log messages
logger.info(f"Backtest started for {strategy.id}")  # Bad
```

---

## Async Patterns

```python
# Good - Async context managers
async with get_db_session() as session:
    result = await session.execute(query)

# Good - Async iteration
async for event in event_stream:
    await process_event(event)

# Good - Task groups for concurrency
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(analyze_data())
    task2 = tg.create_task(compute_risk())
```

---

## Testing Standards

### Test Structure
```python
# Arrange
data = load_test_data("mean_reversion")
strategy = MeanReversionStrategy(parameters)

# Act
results = backtest.run(strategy, data)

# Assert
assert results.sharpe_ratio > 1.0
assert results.max_drawdown < 0.2
assert results.total_trades > 100
```

### Test Naming
```python
# Good - Descriptive test names
def test_mean_reversion_profits_in_ranging_market():
    ...

def test_mean_reversion_loses_in_trending_market():
    ...

# Avoid - Vague test names
def test_strategy():  # Bad
    ...
```

---

## Documentation Standards

### Module Docstrings
```python
"""
Market Data Pipeline

This module handles the acquisition, validation, and storage
of market data from various sources.

Typical usage:
    pipeline = MarketDataPipeline(config)
    data = await pipeline.fetch("RELIANCE", "1d", "2024-01-01", "2024-12-31")
"""
```

### README per Service
Every service/package must have a README.md containing:
- Purpose and scope
- Quick start
- Configuration
- API reference
- Dependencies
- Testing instructions

---

## Error Handling Standards

### Error Classification

| Level | Name | Examples | Action |
|-------|------|---------|--------|
| L0 | Transient | Network timeout, rate limited | Retry with exponential backoff (3 attempts) |
| L1 | Recoverable | Invalid input, missing data | Return error to caller, log, no retry |
| L2 | Critical | DB corruption, broker disconnect | Alert human, pause trading, incident report |
| L3 | Catastrophic | Security breach, constitutional violation | Emergency shutdown, immutable log, human pager |

### Error Response Format

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Retry after 30s.",
    "details": { "retry_after_seconds": 30 },
    "request_id": "req_abc123",
    "timestamp": "2026-07-14T12:00:00Z"
  }
}
```

### Standard Error Codes

| Code | HTTP | Level | Description |
|------|------|-------|-------------|
| `INVALID_INPUT` | 400 | L1 | Malformed request |
| `UNAUTHORIZED` | 401 | L1 | Missing/invalid auth |
| `FORBIDDEN` | 403 | L1 | Insufficient permissions |
| `NOT_FOUND` | 404 | L1 | Resource not found |
| `RATE_LIMITED` | 429 | L0 | Rate limit exceeded |
| `SERVICE_UNAVAILABLE` | 503 | L0 | Engine temporarily down |
| `DEPENDENCY_FAILURE` | 502 | L1 | Downstream failed |
| `INTERNAL_ERROR` | 500 | L2 | Unexpected error |
| `DATA_INTEGRITY` | 500 | L2 | Data corruption |
| `BROKER_DISCONNECT` | 502 | L2 | Broker connection lost |
| `CONSTITUTIONAL_VIOLATION` | 403 | L3 | Violates 12 Laws |

### Graceful Degradation

| Failed Engine | Degraded Behavior |
|---------------|-------------------|
| Data Engine | Use cached data (last 24h), pause new research |
| Risk Engine | Use last known risk snapshot, reduce sizes by 50% |
| Backtest Engine | Queue requests, serve cached results |
| Execution Engine | Pause all trading, alert human |
| Knowledge Graph | Disable graph queries, serve DB fallback |
