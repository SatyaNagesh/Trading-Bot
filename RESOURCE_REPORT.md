# Resource & Memory Leak Detection Report

## Summary

| Metric | Instrumented Value | Threshold | Verdict |
|---|---|---|---|
| Checkpointer Memory Growth | 2,232 KB → 2,258 KB (10 cycles) | < 5% | ✅ PASS |
| SQLite Database Size | 92.0 KB (500 entries) | N/A | ℹ️ INFO |
| IntegratedBot Object Count | 96,862 objects (growth=75,686) | N/A | ⚠️ HIGH |
| File Handle Leak | 129 FDs | < 1024 | ✅ PASS |
| asyncio Task Leak | 0 leaked tasks | 0 | ✅ PASS |

---

## Detailed Breakdown

### 1. Checkpointer Memory Growth

- **Cycles**: 10 iterations
- **Heap Before**: 2,232 KB
- **Heap After**: 2,258 KB
- **Delta**: +26 KB (+1.2%)
- **Verdict**: ✅ PASS

Observations: Each `create_checkpoint()` snapshot serializes every namespace in the ProductionStore, including the growing "checkpoints" namespace, creating O(n²) data growth. At 10 cycles the effect is minimal (+1.2%), but at 100+ cycles growth becomes super-linear.

### 2. PersistenceStore SQLite Database Size

- **Entries**: 500 trades + 16 ProductionStore namespaces (checkpoints, signals, etc.)
- **Database Size**: 92.0 KB
- **Verdict**: ℹ️ INFO

### 3. IntegratedBot Object Count

- **Objects after init**: 96,862
- **Growth from baseline**: 75,686 objects
- **Verdict**: ⚠️ HIGH

Observations: IntegratedBot initialization creates a large number of objects due to multi-component wiring (backtest engine, persistent store, signal optimizer, dashboard, etc.). This is expected for a complex integrated system, but the growth may impact memory-constrained environments.

### 4. File Handle Leak

- **File Descriptors**: 129
- **Threshold**: < 1024 (default ulimit -n)
- **Verdict**: ✅ PASS

Observations: 129 FDs is well within the typical limit. No file handle leak detected.

### 5. asyncio Task Leak

- **Tasks After Init**: 0
- **Verdict**: ✅ PASS

Observations: No lingering asyncio tasks detected after initialization. Note: `IntegratedBot.run_cycle()` was excluded from testing as it hangs on `self.scheduler.next_cycle()`.

---

## Known Issues & Technical Notes

1. **Checkpointer O(n²) Design**: Each checkpoint serializes every namespace in the ProductionStore, causing quadratic growth as the number of checkpoints increases.
2. **IntegratedBot Cycles**: `bot.run_cycle()` hangs indefinitely due to the scheduler state machine requiring prior initialization steps — cycle-based leak tests are not feasible without scheduler refactoring.
3. **Validation Suite**: `packages/tools/validate.py:run()` causes OOM kill and was excluded from profiling.
4. **Backtest Debug Logging**: The `check_stops_not_implemented` message is emitted for every bar (500×) and cannot be suppressed via `logging.disable()` because the project uses a custom stdout handler.
