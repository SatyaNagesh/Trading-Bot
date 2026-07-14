# QuantLab AI — Backtest Engine Specification

> **Simulating Markets**  
> Version 1.0 | Last Updated: July 2026

---

## Section I — Philosophy

### Core Truths

1. **All backtests are wrong, some are useful** — The goal is not perfection but minimizing error
2. **Simulate what you can, acknowledge what you cannot** — Every backtest has blind spots
3. **Transaction costs matter more than you think** — 0.1% per trade compounds to massive gaps
4. **Survivorship bias is the silent killer** — Always test on the universe as it was, not as it is
5. **Overfitting is not optional, it's inevitable** — The question is how much

### Backtest Quality Principles

```yaml
quality:
  - "Use out-of-sample data for final evaluation"
  - "Include all costs: commissions, slippage, spread"
  - "Test across multiple market regimes"
  - "Minimum 500 trades for statistical significance"
  - "Walk-forward validation required"
  - "Monte Carlo simulation for robustness"
  - "Parameter sensitivity analysis"
```

---

## Section II — Engine Architecture

```
┌──────────────────────────────────────────────────┐
│               Backtest Engine                       │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │  Market   │  │  Order   │  │ Position │         │
│  │  Replay   │  │  Manager │  │ Manager  │         │
│  ├──────────┤  ├──────────┤  ├──────────┤         │
│  │ Strategy  │  │  Risk    │  │  P&L     │         │
│  │ Runner    │  │  Filter  │  │ Tracker  │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │           Event Loop Engine                    │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Core Components

| Component | Responsibility |
|-----------|---------------|
| MarketReplay | Feed historical data bar-by-bar |
| OrderManager | Handle order lifecycle |
| PositionManager | Track positions and P&L |
| StrategyRunner | Execute strategy logic per bar |
| RiskFilter | Apply risk rules during simulation |
| PnLTracker | Compute running P&L and metrics |

---

## Section III — Simulation Model

```python
@dataclass
class BacktestConfig:
    initial_capital: Decimal
    start_date: datetime
    end_date: datetime
    commission: Decimal = Decimal("0.0005")   # 0.05%
    slippage: Decimal = Decimal("0.001")      # 0.1%
    spread: Decimal = Decimal("0.0002")       # 0.02%
    margin_rate: Decimal = Decimal("1.0")     # No leverage
    price_type: str = "close"                 # Entry/exit price
    
class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.equity = [config.initial_capital]
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        
    async def run(self, strategy: Strategy, data: pd.DataFrame) -> BacktestResult:
        for timestamp, bar in data.iterrows():
            # 1. Generate signals
            signals = await strategy.generate_signals(bar)
            
            # 2. Apply risk filters
            filtered = await self.risk_filter.check(signals, self.portfolio)
            
            # 3. Execute orders
            for signal in filtered:
                order = self.create_order(signal, bar)
                execution = self.simulate_execution(order, bar)
                if execution.filled:
                    self.process_fill(execution, bar)
            
            # 4. Process exits (stop loss, take profit, time stop)
            await self.process_exits(bar)
            
            # 5. Update portfolio value
            self.update_equity(bar)
            
        return self.compile_results()
```

### Simulation Loop

```
for each bar in historical_data:
    on_bar(bar)
        signals = strategy.next(bar)
        for signal in signals:
            risk_check(signal)
            apply_slippage(order)
            apply_commission(order)
            fill_order(order)
        update_positions(bar)
        update_equity(bar)
        check_stop_losses()
        check_take_profits()
```

---

## Section IV — Market Replay

```yaml
market_replay:
  modes:
    sequential:
      description: "Process bars one by one in chronological order"
      use_case: "Standard backtesting"
      performance: "Accurate but slow"
    
    vectorized:
      description: "Process all bars at once using vector operations"
      use_case: "Fast prototyping"
      performance: "Very fast but limited to simple strategies"
    
    tick_replay:
      description: "Replay tick-by-tick (future V2)"
      use_case: "High-frequency strategies"
      performance: "Most realistic, slowest"

  data_requirements:
    - "Complete data without gaps"
    - "Adjusted for corporate actions"
    - "Survivorship-bias-free universe"
```

---

## Section V — Execution Simulation

### Slippage

```python
def simulate_slippage(price: Decimal, side: str, volume: int, 
                      avg_volume: int, slippage_model: str) -> Decimal:
    if slippage_model == "fixed":
        slippage = price * Decimal("0.001")  # 0.1%
    
    elif slippage_model == "volume_based":
        participation = volume / avg_volume
        slippage = price * min(participation * Decimal("0.01"), Decimal("0.02"))
    
    elif slippage_model == "order_book":
        # Estimate from order book depth (future)
        slippage = price * Decimal("0.001")
    
    return price + slippage if side == "BUY" else price - slippage
```

### Spread

```yaml
spread:
  large_cap: 0.0002    # 0.02%
  mid_cap: 0.0005      # 0.05%
  small_cap: 0.001     # 0.1%
  
  application:
    - "Entry: Use ask price (BUY) or bid price (SELL)"
    - "Exit: Use bid price (SELL) or ask price (BUY)"
```

### Partial Fills

```yaml
partial_fills:
  enabled: true
  fill_probability:
    full: 0.8      # 80% complete fill
    partial: 0.15  # 15% partial fill
    none: 0.05     # 5% no fill
  
  partial_rate:
    high_liquidity: 0.9     # 90% fill
    medium_liquidity: 0.7   # 70% fill
    low_liquidity: 0.5      # 50% fill
```

### Latency

```yaml
latency:
  simulated: true
  delay:
    min: 10ms
    average: 50ms
    max: 200ms
  
  impact:
    - "Order arrives after price moved"
    - "Signal triggered but fill at worse price"
    - "Missed entry/exit in fast markets"
```

### Commission

```yaml
commission:
  structure:
    equity:
      delivery: 0.0001   # 0.01% (DP charges + STT)
      intraday: 0.0003   # 0.03% (brokerage + STT)
    
    futures:
      per_lot: 20         # ₹20 per lot
    
    options:
      per_lot: 50         # ₹50 per lot
  
  minimum_per_order: 10   # Minimum ₹10 per order
  maximum_per_order: 2000  # Maximum ₹2000 per order
```

---

## Section VI — Event-Driven Engine

```python
class EventDrivenBacktest:
    """Event-driven backtest engine for realistic simulation."""
    
    events = {
        "BAR": [],
        "ORDER_FILL": [],
        "ORDER_PARTIAL": [],
        "ORDER_REJECTED": [],
        "STOP_HIT": [],
        "LIMIT_HIT": [],
        "POSITION_OPEN": [],
        "POSITION_CLOSE": [],
        "DIVIDEND": [],
        "CORPORATE_ACTION": [],
    }
    
    def on_bar(self, bar):
        self.emit("BAR", bar)
        self.strategy.on_bar(bar)
        self.check_orders(bar)
        self.check_positions(bar)
    
    def emit(self, event_type, data):
        for handler in self.events.get(event_type, []):
            handler(data)
```

---

## Section VII — Multi-Asset Backtesting

```yaml
multi_asset:
  supported:
    - "Equities (NSE, BSE)"
    - "Futures (underlying + expiry)"
    - "Options (V2)"
    - "ETFs"
    - "Crypto (V2)"
  
  challenges:
    - "Different trading hours"
    - "Different liquidity profiles"
    - "Cross-margining"
    - "Currency conversion"
    - "Corporate actions"
  
  rebalance:
    frequency: "Daily or on signal"
    cash_management: "Reinvest or hold"
```

---

## Section VIII — Walk-Forward Analysis

```yaml
walk_forward:
  windows: 10
  train_ratio: 0.7       # 70% training, 30% testing per window
  min_train_bars: 500
  min_test_bars: 200
  overlap: 0             # No overlap between windows
  
  metrics:
    - "Sharpe decay: in_sample - out_of_sample"
    - "Max drawdown comparison"
    - "Parameter stability"
    - "Win rate consistency"
  
  pass_criteria:
    max_sharpe_decay: 0.5
    max_drawdown_increase: 0.10
    param_stability_score: 0.7
```

### Walk-Forward Algorithm

```python
def walk_forward(strategy: Strategy, data: pd.DataFrame, 
                 windows: int = 10, train_ratio: float = 0.7):
    results = []
    window_size = len(data) // windows
    
    for i in range(windows):
        train_end = int(i * window_size + window_size * train_ratio)
        test_start = train_end + 1
        test_end = int((i + 1) * window_size)
        
        train_data = data[i * window_size:train_end]
        test_data = data[test_start:test_end]
        
        # Optimize on training
        best_params = optimize(strategy, train_data)
        
        # Test on out-of-sample
        result = backtest(strategy, test_data, best_params)
        results.append(result)
    
    return aggregate_walk_forward_results(results)
```

---

## Section IX — Monte Carlo Simulation

```yaml
monte_carlo:
  iterations: 10000
  methods:
    shuffle_returns:
      description: "Shuffle actual returns to test luck hypothesis"
      use: "Test if strategy outperforms random"
    
    synthetic_data:
      description: "Generate synthetic price paths"
      use: "Test robustness across market scenarios"
    
    parameter_perturbation:
      description: "Randomly perturb parameters"
      use: "Test parameter sensitivity"
  
  output:
    - "P-value of strategy outperforming random"
    - "Confidence intervals for Sharpe, returns"
    - "Probability of negative returns"
    - "Worst-case scenario analysis"
```

---

## Section X — Parameter Optimization

### Grid Search

```yaml
grid_search:
  method: "Full factorial"
  parameters:
    lookback: [20, 50, 100, 200]
    threshold: [0.01, 0.02, 0.03]
    stop_loss: [0.01, 0.02, 0.03]
  
  total_runs: 36  # 4 × 3 × 3
  best_by: "sharpe_ratio"
```

### Random Search

```yaml
random_search:
  iterations: 1000
  parameters:
    lookback: { type: int, range: [10, 200] }
    threshold: { type: float, range: [0.005, 0.05] }
    stop_loss: { type: float, range: [0.005, 0.05] }
  
  distribution: "uniform"
  early_stop:
    patience: 50  # Stop if no improvement in 50 iterations
```

### Bayesian Optimization

```yaml
bayesian:
  method: "Gaussian Process"
  acqusition_function: "Expected Improvement"
  initial_points: 20
  iterations: 100
  exploitation_exploration: 0.5  # 50% balance
```

### Optuna Integration

```python
import optuna

def optimize_strategy(strategy_class, data):
    def objective(trial):
        params = {
            "lookback": trial.suggest_int("lookback", 10, 200, step=5),
            "threshold": trial.suggest_float("threshold", 0.005, 0.05, step=0.001),
            "stop_loss": trial.suggest_float("stop_loss", 0.005, 0.05, step=0.001),
        }
        
        strategy = strategy_class(params)
        result = backtest(strategy, data)
        
        # Optimize for Sharpe with penalty for overfitting
        sharpe = result.sharpe_ratio
        complexity_penalty = len(params) * 0.01
        return sharpe - complexity_penalty
    
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=100)
    return study.best_params
```

---

## Section XI — Parallel Computing

```yaml
parallel:
  strategy: "multiprocessing"
  max_workers: 8
  
  workloads:
    - "Multiple parameter combinations simultaneously"
    - "Multiple walk-forward windows simultaneously"
    - "Multiple Monte Carlo iterations simultaneously"
  
  optimization:
    chunk_size: 50
    progress_bar: true
    error_handling: "Skip and log failed runs"
```

---

## Section XII — Report Generation

### Equity Curve

```yaml
equity_curve:
  format: "CSV + JSON + Plotly HTML"
  columns:
    - timestamp
    - portfolio_value
    - cash
    - positions_value
    - daily_return
    - cumulative_return
    - drawdown
```

### Drawdown

```yaml
drawdown:
  metrics:
    - max_drawdown: "Maximum peak-to-trough decline"
    - avg_drawdown: "Average drawdown during losing periods"
    - drawdown_duration: "Days to recover from max drawdown"
    - ulcer_index: "Drawdown depth × duration composite"
```

### Monthly Returns

```yaml
monthly_returns:
  format: "Heatmap (Year × Month)"
  metrics:
    - "Best month: returns"
    - "Worst month: returns"
    - "Positive months: count/ratio"
    - "Consecutive winning months"
    - "Consecutive losing months"
```

### Trade Analysis

```yaml
trade_analysis:
  summary:
    - total_trades
    - winning_trades / losing_trades
    - win_rate
    - avg_win / avg_loss
    - profit_factor
    - avg_holding_period
    - max_consecutive_wins / max_consecutive_losses
  
  distribution:
    - returns_histogram
    - holding_period_histogram
    - trade_by_hour / day / month
```

### Risk Metrics

```yaml
risk_metrics:
  - sharpe_ratio
  - sortino_ratio
  - calmar_ratio
  - sterling_ratio
  - information_ratio
  - alpha / beta
  - r_squared
  - var_95 / cvar_95
```

---

## Section XIII — Benchmarking

```yaml
benchmarking:
  benchmarks:
    - "NIFTY 50 (buy-and-hold)"
    - "BSE Sensex"
    - "NIFTY 500"
    - "Risk-free rate (T-bills)"
  
  metrics:
    - "Excess return over benchmark"
    - "Tracking error"
    - "Information ratio"
    - "Beta / Alpha"
    - "Up/down capture ratio"
    - "Relative drawdown"
  
  visualization:
    - "Strategy vs benchmark equity curve overlay"
    - "Rolling relative performance"
    - "Scatter plot of monthly returns vs benchmark"
```
