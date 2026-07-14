# QuantLab AI — Broker Integration Specification

> **Connecting to Markets**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Broker Integration Layer provides a unified interface for connecting to multiple brokers while abstracting away protocol-specific details.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Trading System                      │
├─────────────────────────────────────────────────────┤
│               Broker Gateway Service                  │
├─────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Zerodha  │  │ Angel One│  │  Alpaca  │          │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │             │             │                  │
│  ┌────▼─────────────▼─────────────▼────┐            │
│  │         Broker API Interface         │            │
│  └──────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

---

## Broker Interface

```python
# packages/broker-api/base.py
class BrokerAPI(ABC):
    """Abstract base class for broker integrations."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection to broker."""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult:
        """Place an order with the broker."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get current positions."""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """Get account information."""
        pass
    
    @abstractmethod
    async def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """Get orders, optionally filtered by status."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get status of a specific order."""
        pass
    
    @abstractmethod
    async def stream_market_data(self, symbols: List[str]) -> AsyncIterator[MarketData]:
        """Stream real-time market data."""
        pass
```

---

## Supported Brokers

### V1 Targets
| Broker | Region | Instruments | API Type |
|--------|--------|-------------|----------|
| Zerodha | India | Equities, F&O | REST + WebSocket |
| Angel One | India | Equities, F&O | REST + WebSocket |

### V2 Targets
| Broker | Region | Instruments | API Type |
|--------|--------|-------------|----------|
| Alpaca | US | Equities | REST + WebSocket |
| Binance | Global | Crypto | REST + WebSocket |

### V3 Targets
| Broker | Region | Instruments | API Type |
|--------|--------|-------------|----------|
| Interactive Brokers | Global | Multi-asset | TWS API / Gateway |
| Upstox | India | Equities, F&O | REST + WebSocket |

---

## Order Model

```python
# packages/broker-api/models/order.py
@dataclass
class Order:
    symbol: str
    exchange: str
    order_type: OrderType  # MARKET, LIMIT, SL, SLM
    side: OrderSide       # BUY, SELL
    quantity: int
    price: Optional[Decimal] = None
    trigger_price: Optional[Decimal] = None
    validity: Validity = Validity.DAY
    tag: Optional[str] = None          # User-defined tag
    strategy_id: Optional[str] = None  # For attribution
    client_id: Optional[str] = None    # For broker mapping
    
@dataclass
class OrderResult:
    order_id: str
    broker_order_id: str
    status: OrderStatus
    filled_quantity: int
    pending_quantity: int
    average_price: Optional[Decimal]
    message: Optional[str]
    timestamp: datetime
```

---

## Environment Tiers

```yaml
tiers:
  sandbox:
    description: "Simulated environment, no real money"
    features:
      - Place orders (simulated)
      - Market data (delayed)
      - No limit checks
    purpose: Development & testing
  
  paper:
    description: "Paper trading with real market conditions"
    features:
      - Place orders (simulated but realistic)
      - Market data (real-time)
      - Full risk management
    purpose: Strategy validation
  
  live:
    description: "Real money trading"
    features:
      - All features enabled
      - Full risk management
      - Compliance monitoring
    purpose: Production
```

---

## Rate Limiting & Throttling

```yaml
rate_limits:
  zerodha:
    orders_per_second: 10
    orders_per_day: 10000
    api_calls_per_second: 50
  
  angel_one:
    orders_per_second: 20
    orders_per_day: 20000
    api_calls_per_second: 100
  
  throttling:
    strategy: token_bucket
    burst_size: 3x steady_rate
    queue: prioritized (critical > high > normal)
```

---

## Error Handling

```python
class BrokerError(Exception):
    def __init__(self, code: str, message: str, broker: str):
        self.code = code
        self.message = message
        self.broker = broker
        super().__init__(f"[{broker}] {code}: {message}")

class RateLimitError(BrokerError): ...
class AuthenticationError(BrokerError): ...
class OrderRejectedError(BrokerError): ...
class InsufficientFundsError(BrokerError): ...
class MarketClosedError(BrokerError): ...
class InstrumentNotFoundError(BrokerError): ...
```

---

## Connection Management

```yaml
connection:
  health_check:
    interval: 30s
    timeout: 5s
    retry: 3
  
  reconnection:
    strategy: exponential_backoff
    initial_delay: 1s
    max_delay: 60s
    max_attempts: 10
  
  failover:
    strategy: switch_to_backup_broker
    criteria:
      - Primary broker unavailable > 60s
      - Error rate > 5% over 5min
      - Manual trigger
```
