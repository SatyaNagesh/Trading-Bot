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
