# QuantLab AI — Research Engine Specification

> **The Scientific Heart**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The Research Engine is the scientific heart of QuantLab AI — responsible for hypothesis formation, experiment design, execution, and result interpretation. It embodies the scientific method in software.

---

## Research Pipeline

```
                                                    ┌─────────────┐
                                                    │  Literature  │
                                                    │   Review    │
                                                    └──────┬──────┘
                                                           │
┌──────────┐    ┌──────────────┐    ┌──────────────┐      │
│  Market   │    │  Hypothesis  │    │  Experiment  │      │
│Observation├───►│  Formation   ├───►│   Design     │◄─────┤
└──────────┘    └──────┬───────┘    └──────┬────────┘      │
                       │                   │               │
                       │              ┌────▼────────┐      │
                       │              │  Data        │      │
                       └──────────────►  Collection  │      │
                                      └────┬────────┘      │
                                           │               │
                                    ┌──────▼───────┐       │
                                    │  Statistical  │       │
                                    │   Analysis    │       │
                                    └──────┬───────┘       │
                                           │               │
                                    ┌──────▼───────┐       │
                                    │   Results     │       │
                                    │ Interpretation│       │
                                    └──────┬───────┘       │
                                           │               │
                                    ┌──────▼───────┐       │
                                    │ Publication / │       │
                                    │  Repository  │───────┘
                                    └──────────────┘
```

---

## Hypothesis Formation

### Hypothesis Template
```yaml
hypothesis:
  id: "hyp_001"
  title: "Monday morning gap reversal in NSE large caps"
  
  description: >
    Stocks that gap up more than 1% in the first 30 minutes
    of trading on Monday tend to reverse their direction by
    the close of the same day.
  
  category: "mean_reversion"
  
  assumptions:
    - Large cap stocks (> 10000 Cr market cap)
    - Gap > 1% in first 30 minutes
    - No major news events on Monday
  
  falsifiable: true
  null_hypothesis: "No relationship between Monday gaps and reversals"
  
  expected_effect:
    direction: "mean_reversion"
    magnitude: "> 0.5% average return"
    timeframe: "close of same day"
  
  market_conditions:
    regimes: ["high_volatility", "neutral"]
    excluded_regimes: ["low_volatility"]
    
  risk_factors:
    - "Black swan events"
    - "Regulatory changes"
    - "Market-wide circuit breakers"
```

### Hypothesis Quality Checklist
```markdown
- [ ] Falsifiable — Can be proven wrong
- [ ] Specific — Clear conditions and measurements
- [ ] Grounded — Based on market observation or theory
- [ ] Novel — Not trivially obvious
- [ ] Testable — Can be tested with available data
- [ ] Economically meaningful — Effect size matters
```

---

## Experiment Design

### Experiment Configuration
```yaml
experiment:
  id: "exp_001"
  hypothesis_id: "hyp_001"
  
  data_requirements:
    symbols: "NIFTY 50 stocks"
    timeframe: "2015-01-01 to 2025-12-31"
    interval: "1m for intraday, 1d for validation"
    minimum_history: "3 years"
  
  methodology:
    type: "backtest"
    engine: "QuantLab Backtest Engine"
  
  parameters:
    gap_threshold: 0.01  # 1%
    lookback_minutes: 30
    hold_period: "close of day"
    position_size: "equal_weight"
    
  controls:
    - "Benchmark: NIFTY 50 index"
    - "Survivorship bias: accounted"
    - "Look-ahead bias: prevented"
    - "Transaction costs: 0.05% per trade"
    
  success_criteria:
    primary:
      metric: "sharpe_ratio"
      threshold: 1.5
    secondary:
      - metric: "win_rate"
        threshold: 0.55
      - metric: "profit_factor"
        threshold: 1.5
    statistical:
      test: "t-test"
      significance: 0.05
      minimum_trades: 1000
```

---

## Statistical Testing

### Test Suite
```python
class StatisticalTestSuite:
    def run_all(self, strategy_results: StrategyResults) -> TestReport:
        tests = [
            self.sharpe_ratio_test(strategy_results),
            self.walk_forward_analysis(strategy_results),
            self.monte_carlo_simulation(strategy_results),
            self.parameter_sensitivity(strategy_results),
            self.regime_stability(strategy_results),
            self.out_of_sample_test(strategy_results),
        ]
        return TestReport(tests=tests)
    
    def walk_forward_analysis(self, results, windows: int = 10):
        """Walk-forward analysis with N windows."""
        scores = []
        for window in range(windows):
            in_sample = results[:len(results) * window // windows]
            out_sample = results[len(results) * window // windows:]
            scores.append({
                "in_sample_sharpe": compute_sharpe(in_sample),
                "out_sample_sharpe": compute_sharpe(out_sample),
                "decay": compute_sharpe(in_sample) - compute_sharpe(out_sample)
            })
        return scores
    
    def monte_carlo_simulation(self, results, iterations: int = 10000):
        """Monte Carlo simulation for robustness."""
        simulated = []
        for _ in range(iterations):
            shuffled = results.sample(frac=1.0)
            simulated.append(compute_sharpe(shuffled))
        return {
            "actual_sharpe": compute_sharpe(results),
            "simulation_mean": np.mean(simulated),
            "simulation_std": np.std(simulated),
            "p_value": self.compute_p_value(compute_sharpe(results), simulated)
        }
```

---

## Result Interpretation

### Research Report Template
```yaml
research_report:
  hypothesis_id: "hyp_001"
  experiment_id: "exp_001"
  
  status: "completed"
  
  results:
    primary_metric:
      sharpe_ratio: 1.82
      passed_threshold: true
    
    secondary_metrics:
      win_rate: 0.58
      profit_factor: 1.75
      max_drawdown: -0.08
      avg_trade_return: 0.0012
    
    statistical:
      p_value: 0.003
      significant: true
      confidence: 0.997
    
    walk_forward:
      windows_completed: 10
      average_decay: 0.15
      stability_score: 0.85
    
  interpretation: >
    The hypothesis is supported by the evidence. The strategy shows
    statistically significant returns with good stability across
    different market periods. The Sharpe ratio of 1.82 exceeds the
    1.5 threshold. Walk-forward analysis shows acceptable decay of 0.15.
    
  recommendation: "proceed_to_validation"
  
  next_steps:
    - "Full validation with expanded parameter testing"
    - "Risk assessment for deployment"
    - "Paper trading for 3 months"
```

---

## Research Repository

```yaml
research_repository:
  storage: PostgreSQL + Knowledge Graph
  
  entries:
    - Published hypotheses
    - Experiment results
    - Literature references
    - Research notes
    - Failed hypotheses
  
  search:
    - By hypothesis category
    - By symbol/market
    - By methodology
    - By result status
    - By author/date
```

---

---

## Section: Validation Engine (Research Engine Sub-Component)

The Validation Engine is a named sub-component of the Research Engine responsible for statistical testing of strategies. See the full spec in `docs/30_RESEARCH_ENGINE_SPEC.md`.

### Key Responsibilities

- Statistical testing (Shapiro-Wilk, t-tests, bootstrap)
- Overfitting detection (combinatorially symmetric cross-validation, deflated Sharpe ratio)
- Walk-forward analysis coordination (executed by Backtest Engine)
- Monte Carlo simulation coordination (executed by Backtest Engine)
- Robustness testing (parameter perturbation, regime shifts)
- Go/no-go recommendation for strategies

### Interface

```python
class ValidationEngine:
    async def validate(
        self, strategy_id: str, backtest_result: BacktestResult
    ) -> ValidationReport: ...
    async def detect_overfitting(
        self, strategy_id: str, results: list[BacktestResult]
    ) -> OverfittingScore: ...
    async def robustness_test(
        self, strategy_id: str, scenarios: list[Scenario]
    ) -> RobustnessReport: ...
    async def recommend(self, strategy_id: str) -> GoNoGo: ...
```

---

## Reproducibility

```yaml
reproducibility:
  recorded:
    - Experiment configuration (full JSON)
    - Data source and version
    - Random seed (42)
    - Software versions (poetry.lock)
    - Git commit hash
    - Execution environment
  
  verification:
    - Run ID matching
    - Result comparison (within floating point tolerance)
    - Automated reproducibility tests
```
