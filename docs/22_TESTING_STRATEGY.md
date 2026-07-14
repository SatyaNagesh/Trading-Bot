# QuantLab AI — Testing Strategy

> **How We Ensure Quality**  
> Version 1.0 | Last Updated: July 2026

---

## Testing Philosophy

- Test behavior, not implementation
- Every test must be deterministic
- Tests are first-class code
- Untested code is broken code
- Coverage is a floor, not a target

---

## Test Levels

### Level 1: Unit Tests
**Purpose**: Verify individual functions/methods
**Scope**: Single function/class
**External Dependencies**: None (mocked)
**Speed**: < 100ms per test
**Location**: `tests/unit/`

```python
def test_calculate_sharpe_with_positive_returns():
    returns = [Decimal("0.01"), Decimal("0.02"), Decimal("0.015")]
    result = calculate_sharpe(returns)
    assert result > 0
```

### Level 2: Integration Tests
**Purpose**: Verify service boundaries
**Scope**: Multiple components
**External Dependencies**: Real databases (test containers)
**Speed**: < 1s per test
**Location**: `tests/integration/`

```python
async def test_data_pipeline_integration():
    async with TestDatabase() as db:
        pipeline = MarketDataPipeline(db)
        await pipeline.fetch_and_store("RELIANCE", "1d")
        assert await db.count_market_data("RELIANCE") > 0
```

### Level 3: Component Tests
**Purpose**: Verify full service behavior
**Scope**: Single service
**External Dependencies**: Real infrastructure (Docker)
**Speed**: < 30s per test
**Location**: `tests/component/`

### Level 4: Contract Tests
**Purpose**: Verify API contracts
**Scope**: API interfaces
**External Dependencies**: Running service
**Speed**: < 5s per test
**Location**: `tests/contract/`

### Level 5: End-to-End Tests
**Purpose**: Verify complete workflows
**Scope**: Multiple services
**External Dependencies**: Full system
**Speed**: < 5min per test
**Location**: `tests/e2e/`

### Level 6: Performance Tests
**Purpose**: Verify performance requirements
**Scope**: Critical paths
**External Dependencies**: Full system
**Speed**: < 10min
**Location**: `tests/performance/`

### Level 7: Security Tests
**Purpose**: Verify security requirements
**Scope**: All security-critical paths
**Frequency**: Every release
**Location**: `tests/security/`

### Level 8: Regression Tests
**Purpose**: Catch regressions
**Scope**: Previously fixed bugs
**Trigger**: When fixing bugs
**Location**: `tests/regression/`

### Level 9: AI Agent Tests
**Purpose**: Verify AI agent behavior
**Scope**: Agent decisions and outputs
**Frequency**: Daily
**Location**: `tests/ai/`

```python
async def test_research_agent_hypothesis_quality():
    agent = ResearchScientistAgent()
    hypothesis = await agent.formulate_hypothesis(market_data)
    
    assert hypothesis.is_falsifiable
    assert hypothesis.has_clear_criteria
    assert hypothesis.confidence > 0.3
```

---

## Test Data Management

### Test Fixtures
```python
# conftest.py
@pytest.fixture
def sample_market_data():
    return pd.DataFrame({
        "open": [100, 101, 102],
        "high": [105, 106, 107],
        "low": [98, 99, 100],
        "close": [102, 103, 104],
        "volume": [1000, 1100, 1200]
    }, index=pd.date_range("2024-01-01", periods=3))

@pytest.fixture
async def test_database():
    db = await TestDatabase.create()
    yield db
    await db.cleanup()
```

### Test Data Storage
```
tests/
├── data/
│   ├── sample_market_data.parquet
│   ├── expected_backtest_results.json
│   └── fixtures/
│       ├── strategies/
│       └── hypotheses/
```

---

## Mocking Strategy

```python
# Good - Mock external interfaces
@pytest.fixture
def mock_broker():
    broker = Mock(spec=BrokerGateway)
    broker.place_order.return_value = OrderResult(
        order_id="test_001",
        status="filled"
    )
    return broker

# Avoid - Mocking domain objects
# Mocking core domain logic is a code smell
```

---

## Coverage Requirements

| Level | Coverage Target | Enforcement |
|-------|----------------|-------------|
| Core packages | 95% | CI failure if below |
| Services | 90% | CI failure if below |
| Agents | 80% | Warning |
| Plugins | 70% | Warning |
| Apps | 80% | CI failure if below |

---

## CI Test Execution

```yaml
# .github/workflows/test.yml
jobs:
  unit:
    run: poetry run pytest tests/unit/ -x --cov=packages
    
  integration:
    run: poetry run pytest tests/integration/ -x
    
  e2e:
    run: poetry run pytest tests/e2e/ -x
    needs: [unit, integration]
```

---

## Test Quality Metrics

| Metric | Target |
|--------|--------|
| Test flakiness | < 0.1% |
| Test execution time (total) | < 15 min |
| Average test speed (unit) | < 100ms |
| Test-to-code ratio | > 1:3 |
| Mutation test score | > 80% |
