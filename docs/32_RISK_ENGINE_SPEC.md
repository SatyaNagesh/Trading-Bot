# QuantLab AI — Risk Engine Specification

> **Protecting Capital**  
> Version 1.0 | Last Updated: July 2026

---

## Section I — Risk Philosophy

### Core Principles

1. **Preservation First** — No trade is worth catastrophic loss
2. **Systematic Constraints** — Risk rules are hard-coded, not advisory
3. **Transparency** — Every risk metric is visible and auditable
4. **Adaptability** — Risk parameters adapt to market conditions
5. **Layering** — Multiple independent risk checks at every level

### Risk Hierarchy

```
┌──────────────────────────────────────────┐
│         Constitutional Risk Limits         │
│  (Hard-coded, cannot be overridden)       │
├──────────────────────────────────────────┤
│         Platform Risk Limits              │
│  (Configured by admin, applies globally)  │
├──────────────────────────────────────────┤
│         Strategy Risk Limits              │
│  (Per-strategy configuration)            │
├──────────────────────────────────────────┤
│         Dynamic Risk Adjustment           │
│  (Real-time adaptation to conditions)     │
└──────────────────────────────────────────┘
```

### Risk Budget

Each strategy is allocated a risk budget:
```yaml
risk_budget:
  max_daily_loss: 0.02       # 2% of capital
  max_monthly_loss: 0.06     # 6% before shutdown
  max_drawdown: 0.20         # 20% peak-to-trough
  max_leverage: 1.0          # No leverage in V1
  min_trades_per_day: 1      # Avoid over-trading
  max_trades_per_day: 20     # Per strategy
```

---

## Section II — Risk Architecture

```
┌──────────────────────────────────────────────────┐
│                  Risk Engine                        │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │Position  │  │Portfolio │  │  Market  │         │
│  │  Risk    │  │   Risk   │  │   Risk   │         │
│  ├──────────┤  ├──────────┤  ├──────────┤         │
│  │Order Risk│  │  AI Risk │  │ Dynamic  │         │
│  ├──────────┤  ├──────────┤  ├──────────┤         │
│  │   Risk   │  │Governance│  │Reporting │         │
│  │Analytics │  │          │  │          │         │
│  └──────────┘  └──────────┘  └──────────┘         │
└──────────────────────────────────────────────────┘
```

### Components

```yaml
PositionSizer:
  - Risk-budget allocation per trade
  - Multiple sizing models
  - Position limit enforcement

PortfolioRisk:
  - Correlation matrix management
  - Sector exposure monitoring
  - Concentration limits
  - Leverage tracking

OrderValidator:
  - Pre-trade validation
  - Duplicate detection
  - Fat finger prevention
  - Margin checks

RiskAnalytics:
  - VaR/CVaR computation
  - Stress testing
  - Scenario analysis
  - Attribution
```

---

## Section III — Position Sizing

### Fixed Size

```python
def fixed_size(capital: Decimal, fixed_amount: Decimal) -> Decimal:
    """Allocate fixed amount per trade."""
    return min(fixed_amount, capital * 0.1)  # Cap at 10%
```

### Kelly Criterion

```python
def kelly(wins: list[float], losses: list[float]) -> float:
    """Full Kelly fraction."""
    w = len(wins) / (len(wins) + len(losses))  # Win probability
    avg_win = mean(wins) if wins else 0
    avg_loss = abs(mean(losses)) if losses else 1
    b = avg_win / avg_loss  # Win/loss ratio
    return (w * (b + 1) - 1) / b
```

### Fractional Kelly

```yaml
fractional_kelly:
  conservative: 0.25  # 25% of full Kelly
  moderate: 0.50      # 50% of full Kelly
  aggressive: 0.75    # 75% of full Kelly
  default: "moderate"
```

### ATR Sizing

```python
def atr_sizing(capital: Decimal, atr: Decimal, risk_percent: float = 0.01) -> int:
    """Size position based on ATR volatility."""
    risk_amount = capital * risk_percent
    position_size = int(risk_amount / atr)
    return position_size
```

### Volatility Targeting

```yaml
volatility_targeting:
  target_vol: 0.15        # 15% annualized volatility target
  lookback: 21            # Trading days for vol estimation
  max_leverage: 2.0       # Maximum scaling factor
  
  calculation: "position_size = (target_vol / current_vol) * base_size"
```

### Risk Parity

```yaml
risk_parity:
  method: "equal_risk_contribution"
  assets: ["strategies", "instruments"]
  rebalance: "monthly"
  constraints:
    - "No single strategy > 25% total risk"
    - "No single sector > 30% total risk"
```

### Equal Weight

```yaml
equal_weight:
  method: "equal_capital"
  rebalance: "quarterly"
  note: "Simplest allocation, used as baseline benchmark"
```

---

## Section IV — Portfolio Risk

### Correlation

```yaml
correlation:
  matrix: "60-day rolling Pearson"
  threshold_alert: 0.7     # Alert if strategies become highly correlated
  threshold_crash: 0.9     # Emergency if correlation spikes
  diversification_target: 0.3  # Target average correlation
  
  monitoring:
    - "Pairwise correlation between active strategies"
    - "Correlation with benchmark"
    - "Correlation regime detection"
```

### Sector Exposure

```yaml
sector_exposure:
  limits:
    banking: 0.30
    technology: 0.25
    pharma: 0.20
    energy: 0.20
    others: 0.15
  
  rebalance: "Weekly or when limit breached"
```

### Market Exposure

```yaml
market_exposure:
  net: "Total long - Total short"
  gross: "Total long + Total short"
  limits:
    max_net_exposure: 1.0
    max_gross_exposure: 2.0
    max_single_name: 0.10
```

### Leverage

| Type | V1 Limit | V2 Limit | V3 Limit |
|------|----------|----------|----------|
| Notional | 1.0x | 2.0x | 3.0x |
| Derivative | 0x | 1.0x | 2.0x |
| Margin used | 50% | 75% | 90% |

### Concentration

```yaml
concentration:
  max_single_strategy: 0.25   # 25% of portfolio
  max_single_stock: 0.10      # 10% of portfolio
  max_industry: 0.30          # 30% of portfolio
  herfindahl_limit: 0.15      # HHI < 0.15 for diversification
```

### Liquidity

```yaml
liquidity:
  min_daily_volume: 1000000    # Min 1 Cr daily turnover
  max_position_pct_volume: 0.01  # Max 1% of daily volume
  max_slippage: 0.001          # Max 0.1% expected slippage
  min_market_cap: 5000         # Min 5000 Cr market cap
```

---

## Section V — Order Risk

### Duplicate Orders

```yaml
duplicate_detection:
  window: 60  # Seconds
  check:
    - "Same symbol"
    - "Same direction"
    - "Same size (±5%)"
    - "Same strategy"
  action: "Block and alert"
```

### Fat Finger Detection

```yaml
fat_finger:
  price_check:
    - "Price within 5% of last traded price"
    - "Price within 10% of VWAP"
    - "Limit price vs market price < 2%"
  
  size_check:
    - "Order size < 5x average trade size"
    - "Order value < 1% of portfolio"
  
  action: "Block if any check fails, require confirmation"
```

### Invalid Prices

```yaml
price_validation:
  checks:
    - "Price > 0"
    - "Price < circuit_limit * 1.1"
    - "Price within bid-ask spread * 3"
    - "Price != 0 or NaN"
  
  action: "Reject order, log error"
```

### Margin Checks

```yaml
margin:
  check: "order_value + existing_margin < available_margin"
  buffer: 0.1        # Maintain 10% margin buffer
  alert_threshold: 0.8  # Alert at 80% margin usage
```

### Position Limits

```yaml
position_limits:
  max_quantity: 10000           # Per order
  max_value: 5000000            # Max order value (₹5 Cr)
  max_positions_per_strategy: 10
  max_positions_portfolio: 50
```

---

## Section VI — Market Risk

### Gap Risk

```yaml
gap_risk:
  detection: "open_price vs previous_close > 2%"
  action:
    - "Pause all orders for 5 minutes"
    - "Re-evaluate open positions"
    - "Check for news events"
```

### Slippage

```yaml
slippage:
  expected:
    large_cap: 0.001     # 0.1% for large caps
    mid_cap: 0.003       # 0.3% for mid caps
    small_cap: 0.005     # 0.5% for small caps
  
  limits:
    max_slippage: 0.01   # Hard limit
    alert_threshold: 0.003  # Warning level
```

### Volatility Spikes

```yaml
volatility_spike:
  detection: "current_atr > 3x average_atr(20)"
  action:
    - "Reduce position sizes by 50%"
    - "Widen stop losses"
    - "Alert risk manager"
```

### News Events

```yaml
news_events:
  scheduled: ["earnings", "budget", "rbi_policy", "fed_meeting"]
  action: "Reduce exposure by 50% 1 hour before major events"
  
  unscheduled: ["natural_disaster", "geopolitical", "regulatory"]
  action: "Close all positions, pause trading"
```

### Circuit Breakers

```yaml
circuit_breakers:
  market_wide:
    - "10% drop: 15-min halt"
    - "15% drop: 30-min halt"
    - "20% drop: Market closed"
  
  action: "Close all positions on halt, wait for resume"
```

---

## Section VII — AI Risk

### Confidence Scoring

```yaml
confidence_scoring:
  scale: 0.0 - 1.0
  thresholds:
    high: "> 0.8"
    medium: "0.5 - 0.8"
    low: "< 0.5"
  
  usage:
    - "High confidence: Full position"
    - "Medium confidence: 50% position"
    - "Low confidence: Requires human review"
```

### Model Disagreement

```yaml
model_disagreement:
  detection: "Multiple ML models give conflicting predictions"
  action:
    - "Reduce position size by 50%"
    - "Flag for human review"
    - "Log predictions from all models"
```

### Hallucination Detection

```yaml
hallucination:
  checks:
    - "Generated strategy DSL parses correctly"
    - "Referenced indicators exist"
    - "Parameter ranges are realistic"
    - "Logic is internally consistent"
    - "Risk constraints are respected"
  
  action:
    - "Reject hallucinated strategy"
    - "Log hallucination pattern"
    - "Retry with stricter constraints"
```

### Unsafe Recommendations

```yaml
unsafe_recommendations:
  blocked:
    - "Penny stock trading"
    - "Options selling (V1)"
    - "Margin trading beyond limits"
    - "Concentrated positions > 25%"
    - "OTC/Pink sheet stocks"
  
  action: "Block recommendation, log violation, notify admin"
```

---

## Section VIII — Dynamic Risk

### Adaptive Position Sizing

```python
def adaptive_size(base_size: Decimal, context: MarketContext) -> Decimal:
    """Adjust position size based on market conditions."""
    adjustments = [
        context.regime_adjustment(),    # Trending = 1.0, Ranging = 0.7
        context.volatility_adjustment(), # Low vol = 1.2, High vol = 0.6
        context.correlation_adjustment(), # Low corr = 1.0, High corr = 0.8
        context.performance_adjustment(), # Winning streak = 1.0, Losing = 0.5
    ]
    
    factor = reduce(operator.mul, adjustments, 1.0)
    return base_size * factor
```

### Regime Detection

```yaml
regime_detection:
  regimes:
    trending:
      sizing_factor: 1.0
      strategies: ["trend_following", "momentum"]
    ranging:
      sizing_factor: 0.7
      strategies: ["mean_reversion", "oscillator"]
    volatile:
      sizing_factor: 0.5
      strategies: ["volatility", "hedged"]
    crisis:
      sizing_factor: 0.0
      strategies: ["cash", "hedged"]
```

### Drawdown Adjustments

```yaml
drawdown_adjustments:
  stages:
    - stage: 1
      drawdown: 0 - 5%
      action: "Normal operations"
    - stage: 2
      drawdown: 5 - 10%
      action: "Reduce position sizes by 25%"
    - stage: 3
      drawdown: 10 - 15%
      action: "Reduce position sizes by 50%, pause new strategies"
    - stage: 4
      drawdown: 15 - 20%
      action: "Close all positions, portfolio review"
    - stage: 5
      drawdown: > 20%
      action: "Emergency shutdown, human intervention required"
```

---

## Section IX — Risk Analytics

### VaR (Value at Risk)

```python
def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical VaR at given confidence level."""
    return np.percentile(returns, (1 - confidence) * 100)

def parametric_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Parametric VaR assuming normal distribution."""
    z = norm.ppf(1 - confidence)
    return returns.mean() + z * returns.std()

def monte_carlo_var(returns: pd.Series, confidence: float = 0.95, 
                    iterations: int = 10000) -> float:
    """Monte Carlo VaR simulation."""
    simulated = np.random.choice(returns, (iterations, len(returns)))
    portfolio_returns = simulated.sum(axis=1)
    return np.percentile(portfolio_returns, (1 - confidence) * 100)
```

### CVaR (Conditional VaR)

```python
def cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """Expected shortfall beyond VaR."""
    var = historical_var(returns, confidence)
    return returns[returns <= var].mean()
```

### Risk Metrics Reference

| Metric | Formula | Interpretation | Target |
|--------|---------|---------------|--------|
| Sharpe | (R_p - R_f) / σ_p | Risk-adjusted return | > 1.5 |
| Sortino | (R_p - R_f) / σ_down | Downside risk-adjusted | > 2.0 |
| Calmar | R_p / |max_dd| | Return vs max drawdown | > 1.0 |
| Max DD | max(peak - trough) | Worst peak-to-trough | < 20% |
| Ulcer | sqrt(mean(drawdown²)) | Drawdown depth × duration | < 10 |
| Profit Factor | gross_profit / gross_loss | Win efficiency | > 1.5 |
| Win Rate | wins / total trades | Percentage profitable | > 45% |

---

## Section X — Governance

### Risk Committee

```yaml
risk_committee:
  members:
    - "Risk Manager Agent"
    - "Portfolio Manager Agent"
    - "System Orchestrator"
    - "Human Project Lead"
  
  meetings:
    - "Daily: Automated risk report review"
    - "Weekly: Strategy risk assessment"
    - "Monthly: Portfolio risk review"
    - "Emergency: Any limit breach"
```

### Reporting

```yaml
reports:
  daily:
    - "Risk metrics summary"
    - "Limit utilization"
    - "Alert log"
  
  weekly:
    - "Strategy-level risk analysis"
    - "Correlation update"
    - "VaR backtest"
  
  monthly:
    - "Portfolio risk deep-dive"
    - "Stress test results"
    - "Risk budget review"
    - "Policy compliance report"
```

### Audit

```yaml
audit:
  - "All risk limit checks are logged immutably"
  - "Any limit override requires human approval"
  - "Monthly risk audit by independent agent"
  - "Quarterly external review (future)"
```
