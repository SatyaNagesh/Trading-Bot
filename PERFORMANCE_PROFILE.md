# Performance Profile Report

## Summary

| Operation | Wall Time | Memory Delta |
|---|---|---|
| Strategy Generation (50) | 5.8 ms | +39.7 KB |
| Backtest (500 bars) | 370.1 ms | +268.0 KB |
| Strategy Ranking | 0.1 ms | +0.4 KB |
| Paper Trading (init) | 0.0 ms | +0.1 KB |
| Analytics (100 trades) | 0.1 ms | +1.5 KB |
| Signal Optimization | 0.0 ms | +0.3 KB |
| Persistence (500 reads) | 21.8 ms | +20.1 KB |
| Dashboard Render | 0.1 ms | +5.2 KB |

**Total time: 3.5 seconds**

---

## Detailed Breakdown

### 1. Strategy Generation (50 strategies)

- **Wall Time**: 5.8 ms
- **Memory Delta**: +39.7 KB
- **Verdict**: ✅ FAST

### 2. Backtest (500 bars)

- **Wall Time**: 370.1 ms
- **Memory Delta**: +268.0 KB
- **Verdict**: ✅ ACCEPTABLE

Observations: The `check_stops_not_implemented` debug message fires once per bar. While these messages do not affect timing accuracy, they produce ~500 lines of log noise per run.

### 3. Strategy Ranking

- **Wall Time**: 0.1 ms
- **Memory Delta**: +0.4 KB
- **Verdict**: ✅ FAST

### 4. Paper Trading Init

- **Wall Time**: 0.0 ms
- **Memory Delta**: +0.1 KB
- **Verdict**: ✅ FAST

### 5. Analytics (100 trades)

- **Wall Time**: 0.1 ms
- **Memory Delta**: +1.5 KB
- **Verdict**: ✅ FAST

### 6. Signal Optimization

- **Wall Time**: 0.0 ms
- **Memory Delta**: +0.3 KB
- **Verdict**: ✅ FAST

### 7. Persistence (500 reads)

- **Wall Time**: 21.8 ms
- **Memory Delta**: +20.1 KB
- **Verdict**: ✅ FAST

### 8. Dashboard Render

- **Wall Time**: 0.1 ms
- **Memory Delta**: +5.2 KB
- **Verdict**: ✅ FAST

---

## Omitted Operations

The following operations from the original script spec were excluded due to technical constraints:

| Operation | Reason |
|---|---|
| Validation Suite | `packages/tools/validate.py:run()` triggers OOM kill |
| IntegratedBot cycles | `bot.run_cycle()` hangs on `self.scheduler.next_cycle()` |
| Checkpointer 100+ cycles | O(n²) data growth makes extended cycles impractical |
