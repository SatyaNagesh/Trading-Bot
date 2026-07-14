# QuantLab AI — Portfolio Engine Specification

> **Managing the Whole**  
> Version 1.0 | Last Updated: July 2026

---

## Section I — Portfolio Philosophy

### Core Principles

1. **Diversification is the only free lunch** — Uncorrelated strategies reduce risk without reducing returns
2. **Risk parity over capital parity** — Allocate by risk contribution, not capital amount
3. **Rebalance with purpose** — Not calendar-based, but threshold-based
4. **Holistic view** — A portfolio is more than the sum of its strategies
5. **Survival first, growth second** — Avoid catastrophic loss above all

### Portfolio Objectives

```yaml
objectives:
  primary:
    - "Preserve capital"
    - "Achieve consistent returns"
    - "Manage drawdowns"
  
  secondary:
    - "Outperform benchmark"
    - "Optimize risk-adjusted returns"
    - "Maintain liquidity"
  
  constraints:
    - "Max drawdown < 20%"
    - "Target Sharpe > 1.0"
    - "Minimum cash reserve: 5%"
```

---

## Section II — Architecture

```
┌──────────────────────────────────────────────────┐
│              Portfolio Engine                       │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │Allocation│  │Rebalancer│  │  Risk    │         │
│  │  Engine  │  │          │  │ Monitor  │         │
│  ├──────────┤  ├──────────┤  ├──────────┤         │
│  │  Cash    │  │Exposure  │  │Portfolio │         │
│  │ Manager  │  │ Manager  │  │Analytics │         │
│  └──────────┘  └──────────┘  └──────────┘         │
└──────────────────────────────────────────────────┘
```

### Components

| Component | Responsibility |
|-----------|---------------|
| AllocationEngine | Determine target allocation per strategy |
| Rebalancer | Execute allocation changes |
| RiskMonitor | Real-time portfolio risk tracking |
| CashManager | Handle cash inflows/outflows |
| ExposureManager | Track sector, instrument, factor exposure |
| PortfolioAnalytics | Compute portfolio-level metrics |

---

## Section III — Portfolio Model

```python
@dataclass
class Portfolio:
    id: str
    name: str
    initial_capital: Decimal
    current_value: Decimal
    cash: Decimal
    strategies: dict[str, StrategyAllocation]  # strategy_id → allocation
    positions: list[Position]
    created_at: datetime
    updated_at: datetime

@dataclass
class StrategyAllocation:
    strategy_id: str
    target_weight: float      # 0.0 - 1.0
    current_weight: float
    risk_contribution: float   # 0.0 - 1.0
    status: str               # active, paused, reducing, exiting
```

---

## Section IV — Allocation Methods

### Equal Weight

```yaml
equal_weight:
  method: "1/N"
  description: "Allocate equal capital to each strategy"
  rebalance: "After strategy addition/removal"
  
  pros:
    - "Simple and transparent"
    - "No estimation errors"
    - "Good baseline"
  
  cons:
    - "Ignores risk differences"
    - "Ignores correlation"
```

### Risk Parity

```python
def risk_parity(cov_matrix: np.ndarray, target_risk: float = 0.15) -> np.ndarray:
    """Equal risk contribution allocation."""
    n = cov_matrix.shape[0]
    
    def risk_contribution(weights):
        portfolio_risk = np.sqrt(weights @ cov_matrix @ weights)
        marginal_contrib = cov_matrix @ weights / portfolio_risk
        risk_contrib = weights * marginal_contrib
        return risk_contrib / portfolio_risk
    
    def objective(weights):
        rc = risk_contribution(weights)
        target = np.ones(n) / n
        return np.sum((rc - target) ** 2)
    
    constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
    bounds = [(0.05, 0.40) for _ in range(n)]  # Min 5%, max 40%
    
    result = minimize(objective, np.ones(n) / n, 
                      method="SLSQP", bounds=bounds, constraints=constraints)
    return result.x
```

### Mean-Variance (Markowitz)

```yaml
mean_variance:
  description: "Maximize Sharpe ratio via mean-variance optimization"
  
  inputs:
    - "Expected returns vector"
    - "Covariance matrix"
    - "Risk-free rate"
  
  challenges:
    - "Estimation error in expected returns"
    - "Estimation error in covariance"
    - "Instability of optimized weights"
    - "Concentration in a few assets"
  
  solutions:
    - "Shrinkage estimation (Ledoit-Wolf)"
    - "Black-Litterman model"
    - "Resampled efficiency"
    - "Robust optimization"
```

### Black-Litterman

```yaml
black_litterman:
  description: "Combine market equilibrium with investor views"
  
  steps:
    1. "Compute market-capitalization weights"
    2. "Reverse-engineer implied returns"
    3. "Specify investor views (confidence-weighted)"
    4. "Combine equilibrium + views via Bayesian approach"
    5. "Optimize resulting expected returns"
  
  advantages:
    - "More stable than mean-variance"
    - "Incorporates investor expertise"
    - "Intuitive weight outputs"
```

### Kelly Portfolio

```yaml
kelly_portfolio:
  description: "Maximize expected log growth"
  
  formula: "f* = (μ - r) / σ²"
  
  challenges:
    - "Aggressive, high volatility"
    - "Requires accurate estimates"
    - "Can suggest > 100% allocation"
  
  modification: "Fractional Kelly (50% recommended)"
```

---

## Section V — Rebalancing

### Rebalance Triggers

```yaml
rebalance_triggers:
  tolerance_based:
    description: "Rebalance when weight drifts beyond threshold"
    threshold: 0.05  # 5% absolute drift
    check_frequency: "Daily"
  
  calendar_based:
    description: "Rebalance on fixed schedule"
    frequency: "Monthly"
    day: 1  # First trading day of month
  
  event_based:
    description: "Rebalance on significant events"
    events:
      - "New strategy added"
      - "Strategy retired"
      - "Large drawdown (> 10%)"
      - "Correlation regime change"
      - "Capital inflow/outflow"
```

### Rebalancing Algorithm

```python
async def rebalance(portfolio: Portfolio, target_weights: dict) -> RebalancePlan:
    trades = []
    current_weights = compute_current_weights(portfolio)
    
    for strategy_id, target in target_weights.items():
        current = current_weights.get(strategy_id, 0)
        drift = target - current
        
        if abs(drift) > REBALANCE_THRESHOLD:
            # Compute required capital movement
            capital_change = portfolio.current_value * drift
            
            # Check constraints
            if constraints_allow(portfolio, strategy_id, capital_change):
                trades.append(Trade(
                    strategy_id=strategy_id,
                    action="increase" if drift > 0 else "decrease",
                    amount=abs(capital_change)
                ))
    
    return RebalancePlan(
        trades=trades,
        estimated_cost=estimate_trading_cost(trades),
        expected_drift_after=0.01  # Remaining drift after rebalance
    )
```

### Rebalance Cost Management

```yaml
rebalance_cost:
  factors:
    - "Commission per trade"
    - "Slippage on large trades"
    - "Market impact"
    - "Tax implications (STT, capital gains)"
  
  optimization:
    - "Batch trades to reduce costs"
    - "Use limit orders for large trades"
    - "Spread rebalance across multiple days"
    - "Netting: offset buys against sells"
  
  cost_benefit:
    threshold: "Only rebalance if expected benefit > 2x estimated cost"
```

---

## Section VI — Cash Management

```yaml
cash_management:
  reserve:
    target: 0.05      # 5% cash reserve
    minimum: 0.02     # Absolute minimum 2%
    maximum: 0.20     # Maximum 20% (inefficient)
  
  deployment:
    method: "Drip feed"
    rate: "10% of cash per day"
    priority:
      - "Fill highest Sharpe strategies first"
      - "Maintain diversification"
      - "Avoid market impact"
  
  withdrawal:
    method: "Reduce proportionally"
    priority:
      - "Reduce lowest Sharpe strategies first"
      - "Minimize tax impact"
      - "Maintain liquidity"
```

---

## Section VII — Multi-Currency

```yaml
multi_currency:
  supported: ["INR", "USD"]
  
  hedging:
    policy: "Hedge 50% of forex exposure"
    instrument: "USD/INR futures"
    frequency: "Monthly"
  
  rebalance:
    include_fx: true
    fx_impact_tracking: true
```

---

## Section VIII — Hedging

### Portfolio-Level Hedging

```yaml
hedging:
  tail_risk:
    description: "Protect against black swan events"
    instrument: "NIFTY put options (OTM)"
    cost: "2-3% of portfolio annually"
    trigger: "VIX > 25"
  
  sector_hedge:
    description: "Hedge concentrated sector exposure"
    instrument: "Sector index futures"
    coverage: "Exposure > 20% in single sector"
  
  duration_hedge:
    description: "Hedge interest rate risk"
    instrument: "Bond futures"
    applicable: "If holding debt instruments"
```

---

## Section IX — Exposure Management

### Factor Exposure

```yaml
factor_exposure:
  factors:
    - "Momentum"
    - "Value"
    - "Size"
    - "Quality"
    - "Low Volatility"
    - "Growth"
  
  limits:
    single_factor: 0.40   # Max 40% in any factor
    factor_diversification: 3  # Minimum 3 factors represented
```

### Exposure Reporting

```yaml
exposure_report:
  dimensions:
    - "By strategy"
    - "By sector"
    - "By market cap"
    - "By factor"
    - "By instrument type"
    - "By currency"
  
  format: "Table + Treemap + Heatmap"
  frequency: "Daily"
```

---

## Section X — Portfolio Analytics

### Core Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Portfolio Return | Σ(weight_i × return_i) | > 15% annualized |
| Portfolio Volatility | √(wᵀΣw) | < 20% |
| Sharpe Ratio | (R_p - R_f) / σ_p | > 1.0 |
| Diversification Ratio | Σσ_i / σ_p | > 1.5 |
| Effective N | 1 / Σ(w_i²) | > 3 |
| Correlation | Average pairwise ρ | < 0.3 |

### Attribution

```yaml
attribution:
  types:
    strategy:
      description: "Contribution of each strategy to total return"
      formula: "strategy_weight × strategy_return"
    
    factor:
      description: "Contribution of each factor to total return"
      method: "Factor regression (Fama-French)"
    
    decision:
      description: "Allocation vs selection effect"
      formula: "Allocation: (w_i - b_i) × R_bi + Selection: w_i × (R_i - R_bi)"
  
  frequency: "Monthly"
```

---

## Section XI — AI Portfolio Optimization

### LLM Portfolio Workflow

```
User Goal → Context → LLM → Allocation Proposal → 
Simulation → Validation → Approval → Execute
```

### AI Constraints

```yaml
ai_portfolio_constraints:
  hard:
    - "Sum of weights = 1.0"
    - "No short selling (V1)"
    - "Max 25% single strategy"
    - "Min 5% cash"
  
  soft:
    - "Target Sharpe > 1.0"
    - "Max drawdown < 20%"
    - "Diversification ratio > 1.5"
```

### Explainability

```yaml
explainability:
  for_each_proposal:
    - "Rationale for each allocation"
    - "Expected risk/return contribution"
    - "Scenario analysis (bull, bear, base)"
    - "Alternative allocations considered"
```

---

## Section XII — Reporting

### Daily Report

```yaml
daily_report:
  sections:
    - "Portfolio summary (value, P&L, return)"
    - "Strategy performance table"
    - "Risk metrics (VaR, drawdown)"
    - "Exposure summary"
    - "Rebalance needed: Yes/No"
    - "Alerts"
```

### Monthly Report

```yaml
monthly_report:
  sections:
    - "Executive summary"
    - "Performance attribution"
    - "Risk analysis"
    - "Rebalance history"
    - "Strategy review (add/remove/modify)"
    - "Forward outlook"
    - "Action items"
```

### Performance Review Template

```markdown
# Portfolio Performance Review - [Month Year]

## Summary
- Return: X%
- Benchmark Return: Y%
- Excess Return: Z%
- Sharpe Ratio: X.X
- Max Drawdown: X%

## Strategy Performance
| Strategy | Weight | Return | Contribution | Sharpe |

## Risk Review
- VaR (95%): X%
- Current Drawdown: X%
- Correlation Matrix: [heatmap]

## Decisions
- Rebalance executed: Yes/No
- Strategies added: 
- Strategies removed:
- Allocation changes:

## Action Items
- [ ] ...
```
