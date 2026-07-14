# QuantLab AI — Observability

> **Seeing the System**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

Observability in QuantLab AI is built on three pillars:
1. **Metrics** — Numerical measurements over time
2. **Logs** — Structured event records
3. **Traces** — Request flow across services

---

## Architecture

```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Service │  │ Service │  │ Service │
│    A    │  │    B    │  │    C    │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  │
          ┌───────▼───────┐
          │ OpenTelemetry  │
          │ Collector      │
          └───────┬───────┘
                  │
     ┌────────────┼────────────┐
     │            │            │
┌────▼────┐ ┌────▼────┐ ┌────▼────┐
│Prometheus│ │  Loki   │ │  Tempo  │
│(Metrics) │ │ (Logs)  │ │(Traces) │
└────┬────┘ └────┬────┘ └────┬────┘
     │            │            │
     └──────┐────┼────────────┘
            │    │
       ┌────▼────▼──┐
       │  Grafana    │
       │ (Dashboard) │
       └────────────┘
```

---

## Metrics

### Instrumentation

```python
from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram

meter = metrics.get_meter("quantlab.backtest")

# Counters
backtest_counter = meter.create_counter(
    "backtest.executions",
    description="Number of backtest executions"
)

trade_counter = meter.create_counter(
    "trades.executed",
    description="Number of trades executed"
)

# Histograms
backtest_duration = meter.create_histogram(
    "backtest.duration",
    description="Backtest execution duration",
    unit="seconds"
)

sharpe_ratio = meter.create_histogram(
    "backtest.sharpe_ratio",
    description="Sharpe ratio distribution"
)

# Gauges
active_strategies = meter.create_gauge(
    "strategies.active",
    description="Number of active strategies"
)

portfolio_value = meter.create_gauge(
    "portfolio.value",
    description="Current portfolio value"
)
```

### Key Metrics

| Category | Metric | Type | Alert Threshold |
|----------|--------|------|-----------------|
| API | request.duration | Histogram | p95 > 500ms |
| API | request.errors | Counter | > 1% |
| API | active.requests | Gauge | > 100 |
| Backtest | execution.duration | Histogram | > 5min |
| Backtest | sharpe_ratio | Histogram | < 1.0 |
| Risk | var.exceedance | Counter | > 0 |
| Risk | drawdown.current | Gauge | > 20% |
| Trading | trade.slippage | Histogram | > 0.1% |
| Trading | order.fill_rate | Histogram | < 95% |
| System | memory.usage | Gauge | > 80% |
| System | cpu.usage | Gauge | > 80% |
| Agents | task.completion | Counter | < 90% |
| Agents | response.time | Histogram | > 30s |

---

## Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Good - Structured with context
logger.info("order_executed",
    order_id=order.id,
    symbol=order.symbol,
    quantity=order.quantity,
    price=order.price,
    execution_time_ms=exec_time,
    strategy_id=strategy.id,
)

# Error with exception info
try:
    result = await process_order(order)
except BrokerError as e:
    logger.error("order_failed",
        order_id=order.id,
        error_code=e.code,
        error_message=str(e),
        exc_info=True,
    )
```

### Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Development details | "Processing bar 1000/5000" |
| INFO | Normal operations | "Backtest completed" |
| WARNING | Unexpected but handled | "Rate limit approaching" |
| ERROR | Operation failure | "Order failed, retrying" |
| CRITICAL | System degradation | "Database connection lost" |

---

## Distributed Tracing

```python
from opentelemetry import trace

tracer = trace.get_tracer("quantlab.research")

async def run_research_pipeline(hypothesis_id: str):
    with tracer.start_as_current_span("research_pipeline") as span:
        span.set_attribute("hypothesis_id", hypothesis_id)
        
        with tracer.start_as_current_span("fetch_data") as fetch_span:
            data = await fetch_market_data()
            fetch_span.set_attribute("data_points", len(data))
        
        with tracer.start_as_current_span("analyze") as analyze_span:
            result = await analyze_hypothesis(data)
            analyze_span.set_attribute("confidence", result.confidence)
        
        return result
```

---

## Alerting Rules

```yaml
# prometheus/alerts.yml
groups:
  - name: quantlab-critical
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_errors_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 1%"
          
      - alert: DrawdownLimitBreached
        expr: portfolio_drawdown > 0.20
        labels:
          severity: critical
        annotations:
          summary: "Portfolio drawdown exceeded 20%"
          
      - alert: RiskLimitApproaching
        expr: risk_vaR_usage > 0.85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "VaR usage at {{ $value }}%"
```

---

## Dashboards

### Grafana Dashboard Layout
```
Row 1: System Health
  - API Request Rate (graph)
  - Error Rate (graph)
  - P95 Latency (graph)
  - Active Workers (stat)

Row 2: Trading
  - Portfolio Value (graph)
  - Strategy Performance (table)
  - Open Positions (table)
  - Risk Metrics (gauges)

Row 3: Research
  - Active Hypotheses (stat)
  - Backtest Queue (graph)
  - Validation Pass Rate (gauge)
  - Agent Activity (table)

Row 4: Infrastructure
  - CPU/Memory Usage (graph)
  - Database Connections (graph)
  - Queue Depth (graph)
  - Disk Usage (gauge)
```

---

## SLIs and SLOs

| SLI | SLO | Measurement |
|-----|-----|-------------|
| API availability | 99.9% | Successful requests / total |
| API latency (p95) | < 200ms | Response time distribution |
| Backtest completion | 99% | Completed / started |
| Trade execution | 99.9% | Successful / attempted |
| Data freshness | 99% | Data < 1min delay |
| Test pass rate | 100% | Passing / total |
