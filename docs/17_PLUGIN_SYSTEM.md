# QuantLab AI — Plugin System

> **Extending the Platform**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Plugin System allows QuantLab AI to be extended with custom functionality without modifying core code. Plugins are sandboxed, versioned, and discoverable.

---

## Plugin Architecture

```
┌────────────────────────────────────────────────────┐
│                  Plugin Host                         │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │           Plugin Manager                       │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐       │  │
│  │  │ Plugin  │ │ Plugin  │ │ Plugin  │       │  │
│  │  │   A     │ │   B     │ │   C     │       │  │
│  │  └────┬────┘ └────┬────┘ └────┬────┘       │  │
│  │       │           │           │              │  │
│  │  ┌────▼───────────▼───────────▼────┐        │  │
│  │  │        Plugin API Layer          │        │  │
│  │  └──────────────────────────────────┘        │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │           Core QuantLab AI System             │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

---

## Plugin Types

### Broker Plugins
Connect to different brokers:
```yaml
type: broker
capabilities:
  - place_order
  - cancel_order
  - get_positions
  - get_account_info
  - stream_market_data
  
examples:
  - zerodha-broker
  - angel-one-broker
  - alpaca-broker
  - ibkr-broker
```

### Data Source Plugins
Provide market data from various sources:
```yaml
type: data-source
capabilities:
  - fetch_historical_data
  - stream_realtime_data
  - get_fundamentals
  - get_corporate_actions

examples:
  - nse-data-source
  - yahoo-finance
  - polygon-io
  - iex-cloud
```

### Indicator Plugins
Technical analysis indicators:
```yaml
type: indicator
capabilities:
  - calculate
  - get_parameters
  - validate_parameters

examples:
  - moving-averages
  - oscillators
  - volume-indicators
  - volatility-indicators
```

### Strategy Plugins
Trading strategy templates:
```yaml
type: strategy
capabilities:
  - generate_signals
  - validate_parameters
  - get_required_data

examples:
  - mean-reversion
  - trend-following
  - breakout
  - statistical-arbitrage
```

### Risk Model Plugins
Risk calculation models:
```yaml
type: risk-model
capabilities:
  - calculate_var
  - calculate_cvar
  - stress_test
  - correlation_analysis

examples:
  - historical-var
  - parametric-var
  - monte-carlo-var
```

---

## Plugin Manifest

Every plugin must include a `plugin.yaml` manifest:

```yaml
name: zerodha-broker
version: 1.0.0
type: broker
author: "QuantLab AI Team"
description: "Zerodha Kite Connect broker integration"

capabilities:
  - place_order
  - cancel_order
  - get_positions

dependencies:
  python:
    - kiteconnect>=5.0.0
  
quantlab:
  min_version: "0.1.0"
  max_version: "1.0.0"

config:
  required:
    - api_key
    - api_secret
  
  optional:
    - user_id
    - twofa_token

permissions:
  - network: ["api.kite.trade"]
  - filesystem: ["read:logs"]
```

---

## Plugin Lifecycle

```
Discovered → Downloaded → Verified → Installed → Active
                │                          │
                ▼                          ▼
            Failed Verification        Inactive → Removed
                                           │
                                       Failed → Error State
```

### Discovery
- Plugin registry (central index)
- Local filesystem
- Git repository
- URL

### Verification
- Signature verification (if signed)
- Dependency check
- Capability validation
- Sandbox compatibility check

### Installation
- Extract to plugin directory
- Install dependencies
- Register with Plugin Manager
- Run initialization hook

### Activation
- Capability registration
- Permission configuration
- Service integration
- Health check

---

## Plugin API

### Core Interface
```python
class QuantLabPlugin:
    """Base class for all plugins."""
    
    @abstractmethod
    def initialize(self, config: dict) -> bool:
        """Initialize plugin with configuration."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if plugin is functioning."""
        pass
    
    def on_activate(self) -> None:
        """Called when plugin is activated."""
        pass
    
    def on_deactivate(self) -> None:
        """Called when plugin is deactivated."""
        pass
    
    def get_capabilities(self) -> list[str]:
        """Return list of capabilities."""
        return self.metadata.get('capabilities', [])
```

### Broker Plugin Interface
```python
class BrokerPlugin(QuantLabPlugin):
    @abstractmethod
    def place_order(self, order: Order) -> OrderResult:
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
    
    @abstractmethod
    def get_positions(self) -> list[Position]:
        pass
    
    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        pass
```

### Indicator Plugin Interface
```python
class IndicatorPlugin(QuantLabPlugin):
    @abstractmethod
    def calculate(self, data: pd.DataFrame, params: dict) -> pd.Series:
        pass
    
    def get_parameters(self) -> dict:
        return self.parameters
    
    def validate_parameters(self, params: dict) -> bool:
        return True
```

---

## Sandboxing

Plugins run in a sandboxed environment:
```yaml
sandbox:
  filesystem:
    read: ["plugin_directory", "shared_data"]
    write: ["plugin_directory/logs"]
    block: ["/etc", "/sys", "/proc"]
    
  network:
    default: block
    allow: ["api.marketdata.com"]
    
  resources:
    cpu_limit: "20%"
    memory_limit: "256MB"
    max_file_size: "10MB"
```

---

## Plugin Marketplace

```yaml
marketplace:
  url: "https://plugins.quantlab.ai"
  
  discovery:
    - featured
    - trending
    - search
    - categories
  
  metrics:
    - downloads
    - rating
    - version
    - compatibility
```

---

## Performance Guidelines

| Plugin Type | Max CPU | Max Memory | Max Latency |
|-------------|---------|------------|-------------|
| Broker | 10% | 128MB | 500ms |
| Data Source | 20% | 256MB | 2s |
| Indicator | 30% | 128MB | 100ms |
| Strategy | 30% | 256MB | 500ms |
| Risk Model | 50% | 512MB | 5s |
