# QuantLab AI — Data Pipeline Specification

> **Data Flow From Source to Storage**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Data Pipeline handles the acquisition, validation, transformation, and storage of all market data used by QuantLab AI.

---

## Pipeline Architecture

```
Raw Data ──► Validator ──► Transformer ──► Storage ──► Serving
    │            │              │             │
    ▼            ▼              ▼             ▼
Data Sources   Quality        Feature       APIs /
               Checks         Engineering   Dashboard
```

---

## Data Sources

### V1 Sources
| Source | Type | Coverage | Frequency | Reliability |
|--------|------|----------|-----------|-------------|
| NSE | Equities | India | Real-time | High |
| BSE | Equities | India | Real-time | High |
| Yahoo Finance | Global | Delayed 15min | Medium |
| Alpha Vantage | Global | API-limited | Medium |

### V2+ Sources
| Source | Type | Coverage |
|--------|------|----------|
| Polygon.io | US equities | Real-time |
| IQFeed | Futures, options | Real-time |
| Bloomberg | Global | Terminal API |
| Quandl | Alternative data | Various |

---

## Data Types

### Market Data
```yaml
ohclv:
  - timestamp
  - open, high, low, close
  - volume
  - vwap
  - trades_count
  interval: [1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk]

tick_data:
  - timestamp
  - price
  - quantity
  - trade_id
  - exchange_timestamp

order_book:
  - timestamp
  - bids: [[price, quantity], ...]
  - asks: [[price, quantity], ...]
  - level: [5, 10, 20]
```

### Fundamental Data
```yaml
company_info:
  - market_cap
  - pe_ratio
  - pb_ratio
  - dividend_yield
  - eps
  - sector
  - industry

financials:
  - revenue
  - net_income
  - total_assets
  - total_liabilities
  - cash_flow
  frequency: quarterly
```

---

## Data Ingestion Pipeline

```python
# services/data-engine/pipeline.py
class DataPipeline:
    async def ingest(self, source: str, symbols: List[str], 
                     data_type: str) -> PipelineResult:
        with tracer.start_as_current_span("data_ingestion"):
            # 1. Fetch raw data
            raw_data = await self.fetch(source, symbols, data_type)
            
            # 2. Validate
            validated = self.validate(raw_data)
            if not validated.is_valid:
                return PipelineResult(failed=True, errors=validated.errors)
            
            # 3. Normalize
            normalized = self.normalize(validated.data)
            
            # 4. Store
            stored = await self.store(normalized)
            
            # 5. Update lineage
            await self.record_lineage(source, symbols, stored)
            
            return PipelineResult(
                failed=False,
                records_stored=stored.count,
                duration=stored.duration
            )
```

---

## Data Validation

```yaml
validation_rules:
  completeness:
    - No missing timestamps within trading hours
    - All required fields present
    - No gaps > 5 minutes for 1m data
    threshold: 99%
    
  consistency:
    - Open <= High, Low <= Close
    - Volume >= 0
    - Price > 0
    - No duplicate timestamps
    
  range:
    - Price within [0.01, 1000000]
    - Volume within [0, 10^10]
    - Returns within [-99%, +INF]
    
  freshness:
    - Realtime data < 1 second old
    - EOD data available by 6 PM IST
    - Historical data < 1 day old
```

---

## Data Storage Architecture

### Partitioning
```sql
-- Daily partition for 1m data
CREATE TABLE market_data_1m (
    LIKE market_data INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- Monthly partition for 1d data
CREATE TABLE market_data_1d (
    LIKE market_data INCLUDING ALL
) PARTITION BY RANGE (timestamp);
```

### Retention Policy
| Data Type | Interval | Retention | Storage |
|-----------|----------|-----------|---------|
| Tick | Real-time | 7 days | PostgreSQL |
| OHLCV | 1m | 1 year | PostgreSQL |
| OHLCV | 1d | 10 years | PostgreSQL + Parquet |
| Fundamentals | Quarterly | 10 years | PostgreSQL |
| Alternative | Various | Project-dependent | S3/MinIO |

---

## Data Lineage

```sql
CREATE TABLE data_lineage (
    id UUID PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    interval VARCHAR(10),
    date_range daterange,
    records_count INTEGER,
    file_hash VARCHAR(64),
    pipeline_version VARCHAR(20),
    quality_score DECIMAL(3,2),
    transformations JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Data Quality Monitoring

```yaml
quality_metrics:
  completeness:
    measurement: "Daily check per symbol per interval"
    alert_threshold: < 95%
    
  accuracy:
    measurement: "Cross-source comparison weekly"
    alert_threshold: > 1% deviation
    
  timeliness:
    measurement: "Delay from market close to availability"
    alert_threshold: > 30 min for EOD
  
  consistency:
    measurement: "OHLCV relationship validation"
    alert_threshold: > 0.1% violations
```

---

## Data Serving APIs

```python
# Internal service API
class DataService:
    async def get_market_data(
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        adjust: bool = True
    ) -> pd.DataFrame:
        """Get market data for analysis."""
        
    async def get_latest_price(
        symbol: str
    ) -> MarketData:
        """Get latest available price."""
        
    async def get_intraday(
        symbol: str,
        interval: str = "1m",
        hours: int = 6
    ) -> pd.DataFrame:
        """Get recent intraday data."""
```
