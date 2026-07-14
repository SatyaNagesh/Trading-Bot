# QuantLab AI — Execution Engine Specification

> **Simulating and Executing Trades**  
> Version 1.0 | Last Updated: July 2026

---

## Section I — Execution Philosophy

### Core Principles

1. **Best Execution** — Achieve the most favorable price considering cost, speed, and likelihood
2. **Fail Safe** — If execution cannot be guaranteed, do not execute
3. **Audit Trail** — Every order, fill, rejection, and cancellation is logged immutably
4. **Latency Awareness** — Order timing matters; simulate delays in backtest, minimize in live
5. **Broker Agnostic** — Execution logic is independent of any specific broker implementation

### Execution vs Broker Gateway

```
Execution Engine:  Strategy → Order Routing → Execution Algorithm → Smart Routing
Broker Gateway:    Normalized Order → Broker API → Broker-specific Protocol
```

The Execution Engine decides *what* and *when* to send. The Broker Gateway handles *how* to send it.

---

## Section II — Architecture

```
┌──────────────────────────────────────────────────┐
│                Execution Engine                     │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │  Order   │  │Execution │  │  Smart   │         │
│  │ Router   │  │  Algo    │  │OrderRouter│         │
│  ├──────────┤  ├──────────┤  ├──────────┤         │
│  │  Order   │  │   Fill   │  │  Order   │         │
│  │ Manager  │  │ Manager  │  │ Status   │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │         Broker Gateway Adapter                 │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Components

```yaml
OrderRouter:
  - Route orders to optimal broker/venue
  - Broker health and latency awareness
  - Fallback broker configuration

ExecutionAlgo:
  - TWAP: Time-weighted average price
  - VWAP: Volume-weighted average price
  - Iceberg: Hidden large orders
  - POV: Percentage of volume

SmartOrderRouter:
  - Multi-venue order splitting
  - Best bid/offer aggregation
  - dark pool routing (V2)

OrderManager:
  - Order lifecycle management
  - Order validation pre-submission
  - Cancel/replace functionality
  - Order persistence

FillManager:
  - Fill aggregation (partial fills)
  - Fill vs order reconciliation
  - Real-time position updates

OrderStatus:
  - Track order state transitions
  - Webhook/event notifications
  - Timeout detection
```

---

## Section III — Order Model

### Order Types

| Type | Fill Guarantee | Price Control | Use Case |
|------|---------------|---------------|----------|
| Market | Immediate | None | Urgent fills |
| Limit | None | Exact price | Price improvement |
| Stop-Loss | Triggered | Market after trigger | Risk management |
| Stop-Limit | Triggered | Limit after trigger | Controlled stops |
| Trailing Stop | Triggered | Dynamic | Trend following |

### Order Lifecycle

```
Created → Validated → Submitted → Pending →
  ├── PartiallyFilled → Pending → ...
  ├── Filled → Complete
  ├── Cancelled → Complete
  └── Rejected → Complete
```

### Order Data Model

```python
@dataclass
class Order:
    id: str
    strategy_id: str
    portfolio_id: str
    symbol: str
    side: str                    # BUY | SELL
    order_type: str              # MARKET | LIMIT | STOP | STOP_LIMIT
    quantity: int
    price: Decimal | None        # Limit/stop price
    time_in_force: str           # DAY | IOC | GTC | FOK
    status: str                  # See lifecycle above
    filled_quantity: int = 0
    average_fill_price: Decimal | None = None
    created_at: datetime
    updated_at: datetime
    broker_order_id: str | None = None
```

---

## Section IV — Execution Algorithms

### TWAP (Time-Weighted Average Price)

```python
def twap(total_quantity: int, duration_minutes: int, slices: int = 10) -> list[Slice]:
    """Split order into equal time slices."""
    slice_size = total_quantity // slices
    interval = duration_minutes / slices
    return [
        Slice(quantity=slice_size, time_offset=interval * i)
        for i in range(slices)
    ]
```

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| slices | 10 | 5-100 | Number of child orders |
| randomization | 0.1 | 0-0.5 | Random offset to avoid pattern detection |
| max_participation | 0.1 | 0.01-0.5 | Max % of volume per slice |

### VWAP (Volume-Weighted Average Price)

```yaml
vwap:
  description: "Schedule orders proportional to historical volume profile"
  inputs:
    - "Historical intraday volume curve (21-day avg)"
    - "Total order quantity"
    - "Start/end time"
  
  algorithm:
    - "Divide trading day into N intervals (e.g., 30-min buckets)"
    - "Compute each bucket's % of total daily volume"
    - "Allocate order quantity proportional to volume %"
    - "Submit child orders at each bucket's open"
```

### Iceberg

```yaml
iceberg:
  description: "Display only small portion of order to hide total size"
  
  parameters:
    display_size: 1000     # Visible portion
    total_quantity: 10000  # Total to execute
    price: 1500.00         # Limit price
    refresh_quantity: 1000 # Replenish after display fills
  
  behavior:
    - "Submit order for display_size at limit price"
    - "When filled, submit new order for display_size"
    - "Repeat until total_quantity filled or cancelled"
```

### POV (Percentage of Volume)

```python
def pov(total_quantity: int, participation_rate: float, 
        volume_forecast: Callable) -> list[Slice]:
    """Participate at fixed % of market volume."""
    slices = []
    remaining = total_quantity
    
    while remaining > 0:
        expected_volume = volume_forecast()
        slice_qty = min(int(expected_volume * participation_rate), remaining)
        slices.append(Slice(quantity=slice_qty))
        remaining -= slice_qty
    
    return slices
```

---

## Section V — Order Routing

### Routing Logic

```yaml
routing:
  primary: "zerodha"
  fallback: "angel_one"
  
  criteria:
    latency: "< 50ms p95"
    cost: "lowest commission"
    reliability: "> 99.9% uptime"
  
  rules:
    - "If primary latency > 100ms, route to fallback"
    - "If primary down > 10s, switch to fallback"
    - "If order > ₹1Cr, split across brokers"
```

### Smart Order Routing

```yaml
smart_routing:
  enabled: true
  venues:
    - "NSE (primary)"
    - "BSE (secondary)"
  
  logic:
    - "Check NSE bid/ask spread"
    - "If NSE spread > 0.05%, check BSE"
    - "Route to venue with tightest spread"
    - "For large orders, split across both"
```

---

## Section VI — Fill Management

### Fill Aggregation

```python
@dataclass
class Fill:
    order_id: str
    fill_id: str
    quantity: int
    price: Decimal
    timestamp: datetime
    venue: str

class FillManager:
    def aggregate_fills(self, order_id: str) -> FillSummary:
        fills = self.get_fills(order_id)
        total_qty = sum(f.quantity for f in fills)
        avg_price = sum(f.quantity * f.price for f in fills) / total_qty
        return FillSummary(
            order_id=order_id,
            total_filled=total_qty,
            avg_price=avg_price,
            fills=fills
        )
```

### Partial Fill Handling

```yaml
partial_fills:
  handling:
    - "Update position immediately on each fill"
    - "Update risk exposure after each fill"
    - "If IOC and partial, cancel remainder"
    - "If DAY and partial, keep working"
  
  notifications:
    - "Emit fill event per partial fill"
    - "Update portfolio engine in real-time"
```

---

## Section VII — Risk Integration

### Pre-Trade Checks

Before submitting any order, the Execution Engine calls the Risk Engine:

```python
async def pre_trade_check(order: Order) -> PreTradeResult:
    checks = await asyncio.gather(
        risk_engine.check_margin(order),
        risk_engine.check_position_limits(order),
        risk_engine.check_duplicate(order),
        risk_engine.check_fat_finger(order),
        risk_engine.check_market_hours(order),
    )
    return PreTradeResult(all(c.passed for c in checks), checks)
```

### Execution Risk Controls

```yaml
execution_risk:
  max_slippage: 0.01           # 1% max slippage tolerance
  max_order_value: 5000000     # ₹5 Cr max per order
  min_order_interval: 100      # ms between orders
  max_open_orders: 20          # Max concurrent open orders
  cancel_on_disconnect: true   # Cancel all on broker disconnect
```

---

## Section VIII — Simulation Mode

### Backtest Integration

```yaml
simulation:
  modes:
    immediate:
      description: "Order fills instantly at expected price"
      use_case: "Fast backtesting"
    
    realistic:
      description: "Simulate latency, partial fills, slippage"
      use_case: "Production-grade backtesting"
    
    replay:
      description: "Replay against recorded order book"
      use_case: "High-fidelity simulation (V2)"

  parameters:
    latency_min_ms: 10
    latency_avg_ms: 50
    latency_max_ms: 200
    fill_rate: 0.95              # 95% fill probability
    partial_fill_rate: 0.15     # 15% partial fills
```

### Simulated Execution

```python
def simulate_execution(order: Order, market: MarketBar, 
                       config: SimulationConfig) -> ExecutionResult:
    latency = random.uniform(config.latency_min_ms, config.latency_max_ms)
    filled, price = simulate_fill(order, market, config)
    
    return ExecutionResult(
        order_id=order.id,
        filled=filled,
        price=price,
        latency_ms=latency,
        slippage=abs(price - market.close) / market.close
    )
```

---

## Section IX — Monitoring

### Execution Metrics

```yaml
metrics:
  - "Order fill rate"
  - "Average slippage (bps)"
  - "Order latency (p50, p95, p99)"
  - "Cancel/replace frequency"
  - "Broker uptime"
  - "Venue routing distribution"

alerts:
  - "Fill rate < 90% in last hour"
  - "Slippage > 10 bps on any order"
  - "Broker disconnected"
  - "Order stuck in pending > 5 minutes"
  - "Cancel rate > 20% in last 10 orders"
```

### Order Book Reconciliation

```yaml
reconciliation:
  frequency: "Every 5 minutes"
  
  checks:
    - "Open orders on broker match local state"
    - "Filled orders on broker exist in local DB"
    - "Position quantities match broker statement"
  
  action_on_mismatch:
    - "Log discrepancy with full context"
    - "Alert human operator"
    - "Do not send new orders until resolved"
```

---

## Section X — Interfaces

### Core Interface

```python
class ExecutionEngine:
    async def execute(self, order: OrderRequest) -> OrderResult: ...
    async def cancel(self, order_id: str) -> bool: ...
    async def replace(self, order_id: str, updates: OrderUpdates) -> OrderResult: ...
    async def get_order(self, order_id: str) -> Order: ...
    async def get_open_orders(self, strategy_id: str | None = None) -> list[Order]: ...
    async def get_positions(self, portfolio_id: str) -> list[Position]: ...
```

### Callback Interface

```python
class ExecutionCallbacks:
    async def on_fill(self, fill: Fill): ...
    async def on_rejection(self, order_id: str, reason: str): ...
    async def on_cancellation(self, order_id: str): ...
    async def on_timeout(self, order_id: str): ...
    async def on_broker_disconnect(self, broker: str): ...
```

### Event Bus Events

| Event | Payload | Emitter |
|-------|---------|---------|
| `order.created` | Order | ExecutionEngine |
| `order.filled` | Fill | ExecutionEngine |
| `order.partially_filled` | Fill | ExecutionEngine |
| `order.rejected` | Order + Reason | ExecutionEngine |
| `order.cancelled` | Order | ExecutionEngine |
| `execution.alert` | Alert | ExecutionEngine |
| `broker.status_change` | Broker + Status | BrokerGateway |
