# QuantLab AI — Strategy Engine Specification

> **Converting Research Into Executable Strategies**  
> Version 1.0 | Last Updated: July 2026

---

## Section I — Strategy Philosophy

### What Is a Strategy?

A trading strategy is a formal, executable specification of:
- **Entry conditions** — When to open a position
- **Exit conditions** — When to close a position
- **Position sizing** — How much to trade
- **Risk rules** — Constraints on the trade
- **Market conditions** — When the strategy is valid

A strategy is NOT a set of indicators glued together. It is a **falsifiable hypothesis** expressed as executable rules.

### Strategy Lifecycle

```
Hypothesis → Research → Strategy → Backtest → Validation → 
Paper Trade → Live Trade → Monitoring → Retirement
```

### Strategy Taxonomy

| Category | Subcategory | Example |
|----------|-------------|---------|
| Trend Following | Momentum, Breakout | Buy when price > 200 SMA |
| Mean Reversion | Oscillator, Pairs | Buy when RSI < 30 |
| Arbitrage | Statistical, Triangle | Pairs cointegration trade |
| Market Making | Liquidity provision | Bid-ask spread capture |
| Event Driven | Earnings, News | Post-earnings drift |
| Volatility | Straddle, Strangle | Long straddle before earnings |
| ML-Based | Classification, Regression | LSTM price prediction |

### Strategy Quality Principles

1. **Parsimony** — Simplest strategy that works is best
2. **Robustness** — Works across market regimes, not curve-fitted
3. **Transparency** — Every rule has a rationale
4. **Testability** — Every condition can be backtested
5. **Survivability** — Survives transaction costs and slippage

### Hypothesis → Strategy Mapping

```yaml
hypothesis:
  "Markets overreact to bad news on Fridays"
    
strategy:
  entry: "SELL if price drops > 2% on Friday AND RSI < 35"
  exit: "BUY to cover on next Tuesday open"
  sizing: "2% risk per trade"
  validity: "Works in bearish and neutral regimes only"
```

---

## Section II — Strategy Architecture

### Strategy Engine Architecture

```
┌──────────────────────────────────────────────────┐
│                Strategy Engine                      │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Strategy  │  │  Signal   │  │ Position │         │
│  │ Manager   │  │ Generator │  │  Sizer   │         │
│  ├──────────┤  ├──────────┤  ├──────────┤         │
│  │ Parameter │  │ Condition │  │ Risk     │         │
│  │ Manager   │  │  Engine   │  │ Filter   │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │           Strategy DSL Interpreter             │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Components

```yaml
StrategyManager:
  - CRUD for strategy definitions
  - Lifecycle management
  - Version control
  - Dependency resolution

SignalGenerator:
  - Evaluate entry/exit conditions
  - Compute signal confidence
  - Handle multi-factor signals
  - Ensemble aggregation

PositionSizer:
  - Apply sizing model
  - Respect risk constraints
  - Handle partial fills
  - Scale in/out

ParameterManager:
  - Hyperparameter definitions
  - Optimization integration
  - Default values
  - Constraint validation

ConditionEngine:
  - Boolean condition evaluation
  - Time-based triggers
  - Market state checks
  - Cross-strategy conditions

RiskFilter:
  - Pre-trade risk check
  - Portfolio correlation check
  - Concentration limits
  - Regime validation
```

### Interfaces

```python
class StrategyEngine:
    async def create_strategy(self, definition: StrategyDef) -> Strategy: ...
    async def get_signals(self, strategy_id: str, market_data: dict) -> Signal: ...
    async def validate(self, strategy_id: str) -> ValidationReport: ...
    async def optimize(self, strategy_id: str, config: OptimConfig) -> OptimResult: ...
```

### Event Flow

```
MarketData → ConditionEngine → SignalGenerator → RiskFilter → Output
     │                              │
     ▼                              ▼
StrategyManager              PositionSizer
```

---

## Section III — Strategy DSL

### Domain Specific Language

Strategies are defined using a structured YAML DSL:

```yaml
strategy:
  id: trend_follow_001
  name: "Trend Following - 50/200 SMA Crossover"
  
  entry:
    conditions:
      - sma(50) > sma(200)
      - volume > sma(volume, 20) * 1.5
      - rsi(14) > 50
    logic: "ALL"  # or "ANY", "AT_LEAST(n)"
    confidence: 0.8
  
  exit:
    conditions:
      - sma(50) < sma(200)
      - stop_loss: 0.02  # 2%
      - take_profit: 0.05  # 5%
  
  sizing:
    model: "risk_based"
    risk_per_trade: 0.01  # 1% of capital
    max_position: 0.1      # 10% of portfolio
  
  filters:
    market_regime: ["trending"]
    min_volume: 1000000
    max_spread: 0.001
```

### Rules

| Rule Type | Description | Example |
|-----------|-------------|---------|
| Price | Price comparison | close > open |
| Indicator | Technical indicator | rsi(14) < 30 |
| Time | Time-based | hour == 9:30 |
| Volume | Volume comparison | volume > avg(20) |
| Pattern | Candlestick pattern | doji(period) |
| External | External signal | news_sentiment > 0.5 |

### Conditions

```python
class Condition:
    def evaluate(self, context: MarketContext) -> bool: ...
    
class AndCondition(Condition):
    def __init__(self, conditions: list[Condition]):
        self.conditions = conditions
    
    def evaluate(self, context) -> bool:
        return all(c.evaluate(context) for c in self.conditions)

class OrCondition(Condition):
    def __init__(self, conditions: list[Condition]):
        self.conditions = conditions
    
    def evaluate(self, context) -> bool:
        return any(c.evaluate(context) for c in self.conditions)
```

### Expressions

```python
# Supported expressions
sma(period)                # Simple moving average
ema(period)                # Exponential moving average
rsi(period)                # Relative Strength Index
macd()                     # MACD line
bb(period, deviations)     # Bollinger Bands
atr(period)                # Average True Range
volume()                   # Current volume
avg(metric, period)        # Average of any metric
highest(period)            # Highest high
lowest(period)             # Lowest low
correl(metric1, metric2)   # Correlation
```

### Indicator API

```python
# packages/indicators/api.py
def sma(data: pd.Series, period: int) -> pd.Series: ...
def ema(data: pd.Series, period: int) -> pd.Series: ...
def rsi(data: pd.Series, period: int = 14) -> pd.Series: ...
def macd(data: pd.Series) -> MACDResult: ...
def bb(data: pd.Series, period: int = 20, std: int = 2) -> BBResult: ...
def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series: ...
```

### Risk API

```python
# Available in DSL as risk.*
risk.max_position_size(portfolio_value, symbol)
risk.max_drawdown(current_equity, peak_equity)
risk.var(returns, confidence=0.95)
risk.cvar(returns, confidence=0.95)
```

### Portfolio API

```python
# Available in DSL as portfolio.*
portfolio.current_exposure(symbol)
portfolio.correlation(strategy_id)
portfolio.allocated_capital()
portfolio.remaining_capacity()
```

---

## Section IV — Signal Generation

### Entry Signals

```yaml
signal:
  type: "entry"
  direction: "long"  # long / short
  confidence: 0.75
  reason:
    - "50 SMA crossed above 200 SMA"
    - "Volume 2x above average"
    - "RSI above 50 confirming momentum"
  metadata:
    indicator_values:
      sma_50: 1542.30
      sma_200: 1521.45
      rsi_14: 58.2
      volume_ratio: 2.1
```

### Exit Signals

| Exit Type | Trigger | Example |
|-----------|---------|---------|
| Stop Loss | Price hits threshold | -2% from entry |
| Take Profit | Price hits target | +5% from entry |
| Trailing Stop | Price reverses from peak | Trail by 1% |
| Time Stop | Position held too long | Exit after 10 days |
| Signal Reverse | Opposite signal fires | Trend reverses |
| Regime Change | Market regime shifts | Trending → Ranging |

### Position Scaling

```yaml
scaling:
  method: "pyramid"
  entries:
    - trigger: "initial_signal"
      percent: 0.5
    - trigger: "price_up_2%"
      percent: 0.3
    - trigger: "price_up_4%"
      percent: 0.2
  
  de_scaling:
    - trigger: "stop_loss_hit"
      action: "exit_all"
    - trigger: "profit_target_met"
      action: "exit_50%"
```

### Signal Confidence

```python
def compute_confidence(signal: Signal, context: MarketContext) -> float:
    score = 0.0
    
    # Indicator alignment
    if all(c.evaluate(context) for c in signal.conditions):
        score += 0.4
    
    # Regime alignment
    if context.regime in signal.valid_regimes:
        score += 0.2
    
    # Volume confirmation
    if context.volume_ratio > 1.5:
        score += 0.2
    
    # Cross-timeframe confirmation
    if signal.confirmed_by_higher_tf:
        score += 0.2
    
    return min(score, 1.0)
```

### Multi-Factor Signals

```yaml
multi_factor:
  factors:
    - name: "momentum"
      weight: 0.4
      signal: positive
      confidence: 0.8
    - name: "value"
      weight: 0.3
      signal: neutral
      confidence: 0.5
    - name: "sentiment"
      weight: 0.3
      signal: positive
      confidence: 0.7
  
  aggregation: "weighted_average"
  threshold: 0.6
```

### Ensemble Signals

```python
class EnsembleSignal:
    def __init__(self, predictors: list[SignalPredictor]):
        self.predictors = predictors
    
    def predict(self, data) -> Signal:
        predictions = [p.predict(data) for p in self.predictors]
        weights = [p.weight for p in self.predictors]
        
        # Weighted average of confidence scores
        avg_confidence = sum(
            p.confidence * w for p, w in zip(predictions, weights)
        ) / sum(weights)
        
        # Majority vote for direction
        direction = mode([p.direction for p in predictions])
        
        # Disagreement measure
        disagreement = compute_disagreement(predictions)
        
        return Signal(
            direction=direction,
            confidence=avg_confidence * (1 - disagreement * 0.5),
            constituents=predictions
        )
```

---

## Section V — Strategy Composition

### Combining Factors

```yaml
composite_strategy:
  name: "Quality Momentum"
  factors:
    - momentum_6m
    - volatility_50d
    - earnings_momentum
  
  combination:
    method: "z_score_sum"
    weights: [0.4, 0.3, 0.3]
    normalize: true
```

### Combining Timeframes

```yaml
multi_tf_strategy:
  higher_tf: "1d"
  lower_tf: "1h"
  
  logic:
    - "Enter only if 1d trend is UP (price > 50 SMA)"
    - "Enter on 1h pullback to 20 EMA"
    - "Exit on 1h stop loss OR 1d trend reversal"
```

### Multi-Asset Strategies

```yaml
multi_asset:
  type: "pairs_trading"
  assets: ["RELIANCE", "TATASTEEL"]
  
  entry: "z-score(spread) > 2.0"
  exit: "z-score(spread) < 0.5"
  stop: "z-score(spread) > 3.0"
```

### Strategy Inheritance

```yaml
parent_strategy:
  id: base_trend_follow
  
child_strategy:
  extends: base_trend_follow
  overrides:
    - entry.stop_loss: 0.03  # Wider stop
    - sizing.risk_per_trade: 0.005  # Half risk
```

### Templates

```yaml
template:
  name: "pullback_trend_follow"
  parameters:
    lookback_period: { type: int, default: 50, min: 20, max: 200 }
    pullback_threshold: { type: float, default: 0.02, min: 0.005, max: 0.05 }
    risk_per_trade: { type: float, default: 0.01, min: 0.001, max: 0.03 }
```

---

## Section VI — Parameter Management

### Hyperparameters

```yaml
parameters:
  lookback:
    type: int
    range: [10, 200]
    step: 5
    default: 50
  
  threshold:
    type: float
    range: [0.001, 0.1]
    step: 0.001
    default: 0.02
  
  stop_loss:
    type: float
    range: [0.005, 0.05]
    default: 0.02
```

### Optimization

| Method | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| Grid Search | Slow | Exhaustive | Small parameter space |
| Random Search | Medium | Good | Large parameter space |
| Bayesian | Fast | Excellent | Expensive evaluations |
| Optuna | Fast | Excellent | Complex constraints |
| Genetic | Medium | Good | Multi-objective |

### Constraints

```yaml
constraints:
  - parameter: stop_loss
    rule: "stop_loss < take_profit"
  - parameter: lookback
    rule: "lookback <= data_length / 2"
  - correlation: [ma_period, signal_period]
    rule: "ma_period > signal_period * 2"
```

### Parameter Validation

```python
def validate_parameters(params: dict) -> ValidationResult:
    errors = []
    warnings = []
    
    for param, value in params.items():
        schema = PARAMETER_SCHEMAS[param]
        if not schema.min <= value <= schema.max:
            errors.append(f"{param}: {value} out of range [{schema.min}, {schema.max}]")
    
    if params["stop_loss"] >= params["take_profit"]:
        errors.append("stop_loss must be < take_profit")
    
    return ValidationResult(errors=errors, warnings=warnings)
```

---

## Section VII — AI Strategy Generation

### LLM Workflow

```
User Request → Context Assembly → Prompt → LLM → Extract → Validate → Refine → Output
```

### Prompt Templates

```markdown
## Task
Design a trading strategy for the following hypothesis:
{hypothesis}

## Market Context
- Asset: {symbol}
- Regime: {regime}
- Volatility: {volatility}
- Available indicators: {indicators}

## Requirements
- Strategy must be expressible in QuantLab DSL
- Include entry, exit, sizing, and risk rules
- Provide confidence level and rationale
- List potential failure modes

## Output Format
```yaml
strategy:
  name: "..."
  entry: { conditions: [...], ... }
  exit: { conditions: [...], ... }
  sizing: { ... }
  risk: { ... }
```
```

### Validation

```yaml
ai_strategy_validation:
  syntax_check: "DSL parses correctly"
  completeness: "All required fields present"
  sanity_check: "Stop < take profit, risk < 5%"
  backtest_required: true
  human_review: "Always required"
```

### Hallucination Detection

```yaml
hallucination_checks:
  - "Indicator exists in available list"
  - "Parameter ranges are valid"
  - "Asset exists in market database"
  - "Strategy logic is internally consistent"
  - "Historical backtest is achievable"
```

### Improvement Loops

```yaml
improvement_loop:
  iterations: 3
  feedback_sources:
    - "Backtest results"
    - "Validation report"
    - "Risk assessment"
    - "Human review"
  
  refinement:
    - "Adjust parameters based on results"
    - "Add risk filters as needed"
    - "Optimize position sizing"
```

---

## Section VIII — Strategy Evaluation

### Statistical Tests

| Test | Purpose | Threshold |
|------|---------|-----------|
| Sharpe Ratio | Risk-adjusted return | > 1.5 |
| T-Test | Returns ≠ 0 | p < 0.05 |
| Walk-Forward | Out-of-sample stability | Decay < 30% |
| Monte Carlo | Robustness | p < 0.05 |

### Robustness

```yaml
robustness:
  tests:
    - "Parameter perturbation (±10%)"
    - "Time period splitting"
    - "Market regime change"
    - "Transaction cost sensitivity"
    - "Slippage sensitivity"
  
  pass_criteria:
    - "Sharpe remains > 1.0 in all tests"
    - "Max drawdown < 25% in all tests"
    - "Win rate > 45% in all tests"
```

### Stability

```yaml
stability:
  metric: "rolling_sharpe_60d"
  requirement: "Standard deviation < 0.5"
  check: "No consecutive losing months > 3"
```

### Complexity Score

```yaml
complexity:
  factors:
    - "Number of parameters: {count, weight: 0.3}"
    - "Number of conditions: {count, weight: 0.3}"
    - "Number of indicators: {count, weight: 0.2}"
    - "Number of regimes: {count, weight: 0.2}"
  
  score:
    low: "< 5"
    medium: "5-15"
    high: "> 15"
    threshold: "Strategies with high complexity require extra validation"
```

### Explainability

Every strategy must produce an explanation:
```yaml
explanation:
  rationale: "Uses momentum following during trending markets"
  logic_flow: "1. Check trend direction → 2. Confirm volume → 3. Enter"
  key_assumptions: "Trend persists for > 5 days"
  failure_cases: "Fails in ranging and high-volatility regimes"
```

---

## Section IX — Strategy Registry

### Metadata

```yaml
strategy:
  id: "strat_042"
  name: "Trend Following SMA Crossover"
  version: 2
  author: "researcher-001"
  created: "2026-01-15"
  updated: "2026-06-20"
  status: "paper_trading"
  
  tags:
    - "trend_following"
    - "nse"
    - "large_cap"
  
  dependencies:
    - indicator: "sma"
    - indicator: "rsi"
    - data: "nse_equity_1d"
```

### Versioning

```yaml
versioning:
  policy: "Semantic versioning"
  major: "Breaking strategy logic changes"
  minor: "Parameter adjustments"
  patch: "Bug fixes, optimizations"
  
  history:
    - version: 2.0.0
      date: "2026-06-20"
      changes: "Added volume filter, reduced drawdown by 15%"
    - version: 1.0.0
      date: "2026-01-15"
      changes: "Initial deployment"
```

### Lineage

```yaml
lineage:
  parent: "hyp_015"
  children: ["strat_043", "strat_044"]
  derived_from: "Literature review of momentum papers"
  targets: ["RELIANCE", "INFY", "HDFCBANK"]
```

---

## Section X — Production Readiness

### Approval Workflow

```
Strategy Created → Self Review → Peer Review → 
Backtest Gate → Risk Gate → Portfolio Gate → 
Paper Trade (30 days) → Performance Review → Live Deploy
```

### Deployment Requirements

```yaml
requirements:
  sharpe_ratio: "> 1.5"
  min_trades: 500
  max_drawdown: "< 20%"
  win_rate: "> 45%"
  walk_forward_pass: true
  monte_carlo_p_value: "< 0.05"
  paper_trade_days: 30
```

### Monitoring

```yaml
monitoring:
  metrics:
    - "Daily P&L"
    - "Sharpe ratio (rolling 60d)"
    - "Max drawdown"
    - "Win rate"
    - "Trade frequency"
  
  alerts:
    - "Drawdown > 15%"
    - "Sharpe < 1.0 for 30 days"
    - "Strategy deviating > 2σ from backtest"
    - "Regime mismatch detected"
  
  review:
    frequency: "Monthly"
    trigger: "Alert or 30-day review cycle"
```

### Retirement

```yaml
retirement:
  triggers:
    - "Drawdown > 25%"
    - "Sharpe < 0.5 for 60 days"
    - "Regime permanently changed"
    - "Better strategy found"
  
  procedure:
    - "Close all positions"
    - "Archive strategy data"
    - "Document lessons learned"
    - "Update knowledge graph"
```
