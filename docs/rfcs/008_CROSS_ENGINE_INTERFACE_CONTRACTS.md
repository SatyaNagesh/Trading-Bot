# RFC-008: Cross-Engine Interface Contracts

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

Several critical interfaces between engines are undefined:

| Interface | Source → Target | Missing |
|-----------|----------------|---------|
| Strategy → Backtest | Strategy Engine → Backtest Engine | How StrategyDef becomes Backtest input |
| Backtest → Validation | Backtest Engine → Validation Engine | BacktestResult schema for validation |
| Portfolio → Execution | Portfolio Engine → Execution Engine | Allocation change → order flow |
| Memory → Knowledge Graph | Memory System → Knowledge Graph | Episodic→Institutional promotion contract |
| Agent → Workflow | Agent Framework → Workflow Engine | How agents start/find/update workflows |
| Data → Research | Data Pipeline → Research Engine | MarketData schema for hypothesis testing |

## Proposed Contracts

### 1. Strategy → Backtest Interface

```python
@dataclass
class BacktestRequest:
    strategy: StrategyDef       # From Strategy Engine
    instruments: list[str]      # Symbols to test on
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    config: BacktestConfig      # Commission, slippage, spread

@dataclass
class BacktestResponse:
    request_id: str
    status: str                 # pending | running | completed | failed
    result: BacktestResult | None
    error: str | None
```

### 2. Backtest → Validation Interface

```python
@dataclass
class ValidationRequest:
    backtest_result: BacktestResult
    config: ValidationConfig    # Confidence level, test types

@dataclass
class ValidationResponse:
    request_id: str
    status: str
    result: ValidationReport | None

@dataclass
class ValidationReport:
    sharpe_test: TestResult
    walk_forward: TestResult
    monte_carlo: TestResult
    robustness: TestResult
    overall_pass: bool
    recommendations: list[str]
```

### 3. Portfolio → Execution Interface

```python
@dataclass
class AllocationOrder:
    portfolio_id: str
    strategy_id: str
    action: str                 # increase | decrease | open | close
    symbol: str
    quantity: int
    order_type: str             # market | limit
    limit_price: Decimal | None
    reason: str                 # rebalance | new_strategy | risk_reduction

@dataclass
class AllocationResponse:
    order_id: str
    status: str
    estimated_cost: Decimal
    execution_plan: list[ExecutionStep]  # For TWAP/VWAP
```

### 4. Memory → Knowledge Graph Promotion

```python
@dataclass
class PromotionRequest:
    source_layer: str           # episodic | semantic
    entries: list[MemoryEntry]
    min_confidence: float = 0.7
    dedup_key: str | None = None

@dataclass
class PromotionResult:
    promoted: int
    skipped: int                # Below confidence or duplicate
    new_nodes: list[str]        # Neo4j node IDs
    new_edges: list[tuple]      # (source, target, type)
```

### 5. Agent → Workflow Engine Interface

```python
class WorkflowEngine:
    async def start_workflow(self, workflow_type: str, params: dict) -> WorkflowInstance: ...
    async def get_workflow_status(self, instance_id: str) -> WorkflowStatus: ...
    async def list_available(self) -> list[WorkflowTemplate]: ...
    async def cancel_workflow(self, instance_id: str) -> bool: ...
```

### 6. Data → Research Interface

```python
@dataclass
class MarketDataRequest:
    instruments: list[str]
    start_date: datetime
    end_date: datetime
    resolution: str             # tick | 1m | 5m | 1d
    adjustments: list[str]      # splits, dividends, corporate_actions

@dataclass
class MarketDataResponse:
    request_id: str
    data: dict[str, pd.DataFrame]  # symbol → OHLCV DataFrame
    quality_report: DataQualityReport
    cache_hit: bool
```

## Changes Required

| Document | Change |
|----------|--------|
| doc 31 | Add BacktestRequest integration section |
| doc 33 | Add BacktestRequest/Response models |
| doc 30 | Add ValidationRequest/Response models |
| doc 34 | Add AllocationOrder interface |
| doc 28 | Add AllocationResponse → Broker adapter |
| doc 11 | Add PromotionRequest/Result to memory consolidation |
| doc 13 | Add Agent→WorkflowEngine interface |
| doc 29 | Add MarketDataRequest/Response schema |
| doc 35 | Reference all interface contracts in Section IX pipeline |

## Action

- [ ] Create shared domain models package (`packages/domain/`) with these contracts
- [ ] Update each engine doc to reference the shared models
